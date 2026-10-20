"""LLM routing: per-task provider/model selection with caching and a per-video budget.

Ported from Clip Creator (same provider set and config shape)."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from typing import TypeVar

from pydantic import BaseModel

from ..config import AppConfig, LLMTaskRoute, load_config
from .base import Budget, BudgetExceeded, LLMError, LLMProvider, LLMResult, ResponseCache, run_structured

log = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)

__all__ = ["Budget", "BudgetExceeded", "LLMError", "LLMResult", "get_provider", "route_for", "complete",
           "is_null", "hold_local_model"]


def get_provider(name: str, cfg: AppConfig | None = None) -> LLMProvider:
    from .providers import AnthropicProvider, GeminiProvider, OllamaProvider, OpenAIProvider

    cfg = cfg or load_config()
    classes = {"anthropic": AnthropicProvider, "openai": OpenAIProvider, "gemini": GeminiProvider,
               "ollama": OllamaProvider}
    if name not in classes:
        raise LLMError(f"Unknown LLM provider '{name}' (choose from {', '.join(classes)} or null)")
    pcfg = cfg.llm.providers.get(name)
    if pcfg is None or not pcfg.enabled:
        raise LLMError(f"LLM provider '{name}' is disabled in config")
    return classes[name](pcfg, cfg)


def route_for(task: str, cfg: AppConfig | None = None, override: str | None = None) -> LLMTaskRoute:
    """Resolve the provider/model for a task. ``override`` is "provider" or "provider:model"."""
    cfg = cfg or load_config()
    route = cfg.llm.tasks.get(task, LLMTaskRoute()).model_copy()
    if override:
        prov, _, model = override.partition(":")
        if prov != route.provider:
            route = LLMTaskRoute(provider=prov, model=model or _default_model(prov, cfg, task),
                                 max_tokens=route.max_tokens)
        elif model:
            route.model = model
    return route


def _default_model(provider: str, cfg: AppConfig, task: str) -> str:
    for r in cfg.llm.tasks.values():
        if r.provider == provider and r.model:
            return r.model
    return "claude-opus-5-5" if provider == "anthropic" else ""


def is_null(route: LLMTaskRoute) -> bool:
    return route.provider in ("null", "none", "")


def complete(task: str, system: str, user: str, schema: type[T], *, route: LLMTaskRoute,
             budget: Budget | None = None, cfg: AppConfig | None = None, use_cache: bool = True) -> LLMResult[T]:
    cfg = cfg or load_config()
    if budget:
        budget.check()
    provider = get_provider(route.provider, cfg)
    cache = ResponseCache(cfg.paths.data / "llm_cache") if use_cache else None
    res = run_structured(provider, system, user, schema, route, cache)
    if budget:
        budget.charge(res, task)
    log.info("llm %s via %s:%s - %d in / %d out tokens, $%.4f%s", task, res.provider, res.model,
             res.input_tokens, res.output_tokens, res.cost_usd, " (cached)" if res.cached else "")
    return res


@contextmanager
def hold_local_model(route: LLMTaskRoute, cfg: AppConfig | None = None) -> Iterator[None]:
    """Keep a local (Ollama) model in VRAM across many calls, then free it. A no-op for cloud providers."""
    if route.provider != "ollama":
        yield
        return
    from .providers import OLLAMA_KEEP_ALIVE

    token = OLLAMA_KEEP_ALIVE.set("10m")
    try:
        yield
    finally:
        OLLAMA_KEEP_ALIVE.reset(token)
        try:
            get_provider("ollama", cfg).unload(route.model)
        except LLMError as e:
            log.warning("Could not unload %s: %s", route.model, e)
