"""What the script writer (LLM) must return. Kept flat so small local models fill it reliably."""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, Field, create_model

from ..config import PROJECT_ROOT

ICONS_JSON = PROJECT_ROOT / "video" / "src" / "icons.json"


@lru_cache(maxsize=1)
def icon_names() -> tuple[str, ...]:
    """Icon names the video can draw (shared with video/src/icons.json)."""
    try:
        return tuple(json.loads(ICONS_JSON.read_text(encoding="utf-8")).keys())
    except (OSError, ValueError):
        return ("news", "chip", "phone", "ai", "money", "shield", "rocket", "game")


@lru_cache(maxsize=1)
def draft_model() -> type[BaseModel]:
    IconName = Literal[("",) + icon_names()]  # type: ignore[valid-type]

    VisualDraft = create_model(
        "VisualDraft",
        type=(Literal["headline", "stat", "icon", "versus", "bullets"], Field(
            description="headline: short punchy on-screen line; stat: one key number; icon: a concept with a "
                        "drawn icon; versus: two things compared; bullets: 2-3 short points")),
        text=(str, Field(description="headline: 3-8 word on-screen headline. icon: 2-6 word label. Otherwise empty.")),
        value=(str, Field(description="stat only: the number exactly as it should appear, e.g. $5T, 30%, 2.5x, 1M")),
        label=(str, Field(description="stat: what the number measures (2-6 words). versus: what is compared "
                                      "(2-6 words). Otherwise empty.")),
        trend=(Literal["up", "down", "none"], Field(description="stat only: up/down if the number rose/fell")),
        icon=(IconName, Field(description="icon only: the best matching icon name; empty for other types")),
        left=(str, Field(description="versus only: first thing (1-3 words)")),
        right=(str, Field(description="versus only: second thing (1-3 words)")),
        items=(list[str], Field(description="bullets only: 2-3 items, each 2-5 words")),
    )

    SceneDraft = create_model(
        "SceneDraft",
        narration=(str, Field(description="What the narrator says over this visual: 1-2 short spoken sentences.")),
        visual=(VisualDraft, ...),
    )

    return create_model(
        "ScriptDraft",
        title=(str, Field(description="Video title, max 80 characters, factual, no clickbait or ALL CAPS")),
        topic=(str, Field(description="One or two words for the topic stamp, e.g. AI, Phones, Security, Gaming")),
        scenes=(list[SceneDraft], Field(description="4-6 scenes in order. The first is the hook and uses a "
                                                    "headline visual.")),
        outro=(str, Field(description="One short spoken closing line: why it matters or a question for viewers")),
        description=(str, Field(description="1-2 sentence video description")),
        hashtags=(list[str], Field(description="3-6 relevant hashtags without the # sign")),
    )
