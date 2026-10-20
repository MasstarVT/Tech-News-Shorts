"""Provider-neutral structured-output interface, response cache, and cost budget."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Generic, TypeVar

from pydantic import BaseModel, ValidationError

from ..config import AppConfig, LLMProviderConfig, LLMTaskRoute

log = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)

# USD per million tokens (input, output). Override/extend via config `llm.pricing`.
DEFAULT_PRICING: dict[str, tuple[float, float]] = {
    "claude-fable-5-1": (10.0, 50.0),
    "claude-opus-5-5": (4.0, 20.0),
    "claude-opus-5": (5.0, 25.0),
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-sonnet-5": (2.0, 10.0),
    "claude-haiku-4-5": (1.0, 5.0),
}


class LLMError(RuntimeError):
    pass


class BudgetExceeded(LLMError):
    pass


@dataclass
class LLMResult(Generic[T]):
    data: T
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_s: float = 0.0
    cached: bool = False


@dataclass
class RawCompletion:
    text: str
    input_tokens: int = 0
    output_tokens: int = 0
    parsed: BaseModel | None = None
    model: str = ""


@dataclass
class Budget:
    limit_usd: float
    spent_usd: float = 0.0
    calls: list[dict] = field(default_factory=list)

    def charge(self, res: LLMResult, task: str) -> None:
        self.spent_usd += res.cost_usd
        self.calls.append({"task": task, "provider": res.provider, "model": res.model, "in": res.input_tokens,
                           "out": res.output_tokens, "usd": round(res.cost_usd, 5), "cached": res.cached,
                           "latency_s": round(res.latency_s, 2)})

    def check(self) -> None:
        if self.limit_usd > 0 and self.spent_usd >= self.limit_usd:
            raise BudgetExceeded(f"LLM budget of ${self.limit_usd:.2f} reached (spent ${self.spent_usd:.2f})")


class LLMProvider(ABC):
    name = "base"

    def __init__(self, pcfg: LLMProviderConfig, cfg: AppConfig):
        self.pcfg = pcfg
        self.cfg = cfg

    @abstractmethod
    def complete(self, system: str, user: str, schema: type[BaseModel], route: LLMTaskRoute) -> RawCompletion:
        """Return JSON text (and optionally an already-parsed object) matching ``schema``."""

    @abstractmethod
    def list_models(self) -> list[str]: ...

    def price(self, model: str) -> tuple[float, float]:
        table = {**DEFAULT_PRICING, **{k: tuple(v) for k, v in self.cfg.llm.pricing.items()}}
        if model in table:
            return table[model]
        for k, v in table.items():
            if model.startswith(k):
                return v
        return (0.0, 0.0)


def strict_schema(schema: type[BaseModel]) -> dict:
    """JSON schema with $defs inlined and additionalProperties:false everywhere."""
    js = schema.model_json_schema()
    defs = js.pop("$defs", {})

    def inline(node):
        if isinstance(node, dict):
            if "$ref" in node:
                return inline(defs[node["$ref"].split("/")[-1]])
            # drop the "title"/"default" annotations, but not properties that happen to be named title
            out = {k: ({name: inline(sub) for name, sub in v.items()} if k == "properties" else inline(v))
                   for k, v in node.items() if k not in ("title", "default")}
            if out.get("type") == "object":
                out["additionalProperties"] = False
                out["required"] = list(out.get("properties", {}).keys())
            return out
        if isinstance(node, list):
            return [inline(x) for x in node]
        return node

    return inline(js)


class ResponseCache:
    def __init__(self, directory: Path):
        self.dir = directory
        self.dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def key(provider: str, route: LLMTaskRoute, system: str, user: str, schema: type[BaseModel]) -> str:
        h = hashlib.sha256()
        for part in (provider, route.model, str(route.temperature), str(route.effort), system, user,
                     json.dumps(schema.model_json_schema(), sort_keys=True)):
            h.update(part.encode("utf-8"))
            h.update(b"\x00")
        return h.hexdigest()[:32]

    def get(self, key: str) -> dict | None:
        p = self.dir / f"{key}.json"
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return None
        return None

    def put(self, key: str, value: dict) -> None:
        (self.dir / f"{key}.json").write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def run_structured(provider: LLMProvider, system: str, user: str, schema: type[T], route: LLMTaskRoute,
                   cache: ResponseCache | None = None, max_fix_attempts: int = 2) -> LLMResult[T]:
    """Call a provider, validate the JSON against ``schema``, feed validation errors back on failure."""
    ck = ResponseCache.key(provider.name, route, system, user, schema) if cache else ""
    if cache and (hit := cache.get(ck)):
        try:
            return LLMResult(schema.model_validate(hit["data"]), provider.name, hit.get("model", route.model),
                             cached=True)
        except ValidationError:
            pass

    prompt = user
    last_err = ""
    total_in = total_out = 0
    t0 = time.time()
    for attempt in range(max_fix_attempts + 1):
        raw = provider.complete(system, prompt, schema, route)
        total_in += raw.input_tokens
        total_out += raw.output_tokens
        try:
            if isinstance(raw.parsed, schema):
                data = raw.parsed
            else:
                data = schema.model_validate_json(_extract_json(raw.text))
            pin, pout = provider.price(raw.model or route.model)
            res = LLMResult(data, provider.name, raw.model or route.model, total_in, total_out,
                            (total_in * pin + total_out * pout) / 1e6, time.time() - t0)
            if cache:
                cache.put(ck, {"data": data.model_dump(mode="json"), "model": res.model})
            return res
        except (ValidationError, ValueError) as e:
            last_err = str(e)[:1500]
            log.warning("%s returned invalid JSON (attempt %d): %s", provider.name, attempt + 1, last_err[:200])
            prompt = (f"{user}\n\nYour previous answer was not valid for the required JSON schema. "
                      f"Validation error:\n{last_err}\nReturn ONLY corrected JSON.")
    raise LLMError(f"{provider.name}: could not get valid structured output: {last_err}")


def _extract_json(text: str) -> str:
    s = text.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else s
        s = s.rsplit("```", 1)[0]
    start = min((i for i in (s.find("{"), s.find("[")) if i >= 0), default=-1)
    if start > 0:
        s = s[start:]
    return s.strip()
