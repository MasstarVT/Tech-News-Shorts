"""Script stage: story -> narration + on-screen visuals."""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from ..config import AppConfig
from ..llm import Budget, complete, is_null, route_for
from ..models import Script, Story
from . import fallback
from .normalize import ScriptError, build_script
from .schema import draft_model, icon_names

log = logging.getLogger(__name__)

__all__ = ["ScriptError", "write_script", "prompts"]

MAX_CONTEXT = 6500


@lru_cache(maxsize=1)
def _env() -> Environment:
    return Environment(loader=FileSystemLoader(Path(__file__).parent / "prompts"), undefined=StrictUndefined,
                       keep_trailing_newline=True)


def prompts(story: Story, cfg: AppConfig) -> tuple[str, str]:
    sc = cfg.script
    words_per_s = cfg.voice.words_per_s
    system = _env().get_template("system.j2").render(
        min_words=sc.min_words, max_words=sc.max_words, style=sc.style, source=story.source,
        min_s=round(sc.min_words / words_per_s), max_s=round(sc.max_words / words_per_s),
    )
    system += "\nAllowed icon names: " + ", ".join(icon_names())
    context = story.context[:MAX_CONTEXT] or "(no article text - use only the headline)"
    user = _env().get_template("user.j2").render(
        source=story.source, also_in=", ".join(story.also_in), title=story.title, url=story.url,
        published=f"{story.published:%Y-%m-%d}" if story.published else "unknown", context=context,
    )
    return system, user


def write_script(story: Story, cfg: AppConfig, override: str | None = None) -> Script:
    route = route_for("script", cfg, override)
    if is_null(route):
        return build_script(fallback.draft(story), story, cfg, llm="null")
    system, user = prompts(story, cfg)
    res = complete("script", system, user, draft_model(), route=route, budget=Budget(cfg.llm.budget_usd_per_video), cfg=cfg)
    return build_script(res.data.model_dump(), story, cfg, llm=f"{res.provider}:{res.model}")
