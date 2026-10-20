"""Concrete LLM providers: Anthropic (Claude), OpenAI (GPT), Google (Gemini), Ollama (local)."""

from __future__ import annotations

import logging
import time
from contextvars import ContextVar

import httpx
from pydantic import BaseModel

from ..config import LLMTaskRoute, secret
from .base import LLMError, LLMProvider, RawCompletion, strict_schema

log = logging.getLogger(__name__)


def _need_model(route: LLMTaskRoute, provider: str) -> str:
    if not route.model:
        raise LLMError(f"No model configured for provider '{provider}'. Set llm.tasks.<task>.model in "
                       f"config/config.yaml (see `technews llm models {provider}`).")
    return route.model


# --------------------------------------------------------------------------- Anthropic


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def _client(self):
        import anthropic

        key = secret(self.pcfg.api_key_env)
        kwargs = {"api_key": key} if key else {}  # else: SDK resolves env / `ant auth login` profile
        if self.pcfg.base_url:
            kwargs["base_url"] = self.pcfg.base_url
        return anthropic.Anthropic(**kwargs)

    def complete(self, system: str, user: str, schema: type[BaseModel], route: LLMTaskRoute) -> RawCompletion:
        model = route.model or "claude-opus-5-5"
        client = self._client()
        output_config = {"effort": route.effort} if route.effort else {}
        kwargs = {}
        if output_config:
            kwargs["output_config"] = output_config
        # Server-side refusal fallback: if a safety classifier declines, the API re-runs the
        # request on Anthropic's recommended fallback model instead of returning a refusal.
        resp = client.beta.messages.parse(
            model=model,
            max_tokens=route.max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_format=schema,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            **kwargs,
        )
        if resp.stop_reason == "refusal":
            detail = getattr(resp, "stop_details", None)
            raise LLMError(f"Claude declined the request ({getattr(detail, 'category', None)})")
        if resp.stop_reason == "max_tokens":
            raise LLMError("Claude hit max_tokens before finishing; raise llm.tasks.<task>.max_tokens")
        text = next((b.text for b in resp.content if b.type == "text"), "")
        return RawCompletion(text=text, input_tokens=resp.usage.input_tokens, output_tokens=resp.usage.output_tokens,
                             parsed=resp.parsed_output, model=resp.model or model)

    def list_models(self) -> list[str]:
        return [m.id for m in self._client().models.list()]


# --------------------------------------------------------------------------- OpenAI


class OpenAIProvider(LLMProvider):
    name = "openai"

    def _client(self):
        import openai

        kwargs = {}
        if key := secret(self.pcfg.api_key_env):
            kwargs["api_key"] = key
        if self.pcfg.base_url:
            kwargs["base_url"] = self.pcfg.base_url
        return openai.OpenAI(**kwargs)

    def complete(self, system: str, user: str, schema: type[BaseModel], route: LLMTaskRoute) -> RawCompletion:
        model = _need_model(route, self.name)
        kwargs: dict = {"max_output_tokens": route.max_tokens}
        if route.temperature is not None:
            kwargs["temperature"] = route.temperature
        if route.effort:
            kwargs["reasoning"] = {"effort": route.effort}
        resp = self._client().responses.parse(
            model=model,
            input=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            text_format=schema,
            **kwargs,
        )
        usage = getattr(resp, "usage", None)
        return RawCompletion(
            text=resp.output_text or "",
            input_tokens=getattr(usage, "input_tokens", 0) or 0,
            output_tokens=getattr(usage, "output_tokens", 0) or 0,
            parsed=resp.output_parsed,
            model=getattr(resp, "model", model),
        )

    def list_models(self) -> list[str]:
        return sorted(m.id for m in self._client().models.list())


# --------------------------------------------------------------------------- Gemini


class GeminiProvider(LLMProvider):
    name = "gemini"

    def _client(self):
        from google import genai

        key = secret(self.pcfg.api_key_env) or secret("GOOGLE_API_KEY")
        return genai.Client(api_key=key) if key else genai.Client()

    def complete(self, system: str, user: str, schema: type[BaseModel], route: LLMTaskRoute) -> RawCompletion:
        from google.genai import types

        model = _need_model(route, self.name)
        cfg_kwargs: dict = {
            "system_instruction": system,
            "response_mime_type": "application/json",
            "response_json_schema": strict_schema(schema),
            "max_output_tokens": route.max_tokens,
        }
        if route.temperature is not None:
            cfg_kwargs["temperature"] = route.temperature
        resp = self._client().models.generate_content(
            model=model, contents=user, config=types.GenerateContentConfig(**cfg_kwargs)
        )
        um = getattr(resp, "usage_metadata", None)
        return RawCompletion(
            text=resp.text or "",
            input_tokens=getattr(um, "prompt_token_count", 0) or 0,
            output_tokens=(getattr(um, "candidates_token_count", 0) or 0) + (getattr(um, "thoughts_token_count", 0) or 0),
            model=model,
        )

    def list_models(self) -> list[str]:
        out = []
        for m in self._client().models.list():
            actions = getattr(m, "supported_actions", None) or []
            if not actions or "generateContent" in actions:
                out.append(m.name.removeprefix("models/"))
        return sorted(out)


# --------------------------------------------------------------------------- Ollama (local)

# Set by llm.hold_local_model() so a batch of calls doesn't reload the model from disk every time.
OLLAMA_KEEP_ALIVE: ContextVar[int | str] = ContextVar("ollama_keep_alive", default=0)


class OllamaProvider(LLMProvider):
    name = "ollama"

    @property
    def base(self) -> str:
        return (self.pcfg.base_url or "http://127.0.0.1:11434").rstrip("/")

    def complete(self, system: str, user: str, schema: type[BaseModel], route: LLMTaskRoute) -> RawCompletion:
        import json

        model = _need_model(route, self.name)
        js = strict_schema(schema)
        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": f"{system}\n\nRespond with JSON matching this schema:\n{json.dumps(js)}"},
                {"role": "user", "content": user},
            ],
            "format": js,
            "stream": False,
            "options": {"temperature": route.temperature if route.temperature is not None else 0.0,
                        "num_predict": route.max_tokens, "num_ctx": 16384},
            # free VRAM right away (unless a batch holds the model)
            "keep_alive": OLLAMA_KEEP_ALIVE.get(),
        }
        if route.effort:
            body["think"] = route.effort != "none"
        for attempt in (1, 2):
            try:
                r = httpx.post(f"{self.base}/api/chat", json=body, timeout=900)
                r.raise_for_status()
                break
            except httpx.HTTPStatusError as e:
                # Ollama answers 500 when its model server crashes while loading; a second load usually works
                if attempt == 1 and e.response.status_code >= 500:
                    log.warning("Ollama returned %s - retrying once", e.response.status_code)
                    time.sleep(3)
                    continue
                raise LLMError(f"Ollama request failed ({self.base}): {e}") from e
            except httpx.HTTPError as e:
                raise LLMError(f"Ollama request failed ({self.base}): {e}") from e
        d = r.json()
        return RawCompletion(text=d.get("message", {}).get("content", ""), input_tokens=d.get("prompt_eval_count", 0),
                             output_tokens=d.get("eval_count", 0), model=model)

    def unload(self, model: str) -> None:
        try:
            httpx.post(f"{self.base}/api/generate", json={"model": model, "keep_alive": 0}, timeout=60)
        except httpx.HTTPError as e:
            log.warning("Could not unload Ollama model %s: %s", model, e)

    def list_models(self) -> list[str]:
        r = httpx.get(f"{self.base}/api/tags", timeout=5)
        r.raise_for_status()
        return sorted(m["name"] for m in r.json().get("models", []))
