"""Stories already turned into videos, so the same news isn't covered twice."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from rapidfuzz import fuzz

from ..config import AppConfig
from ..models import Story

SIMILAR = 82  # token_set_ratio at or above this counts as the same story


def _path(cfg: AppConfig) -> Path:
    return cfg.paths.data / "history.json"


def load(cfg: AppConfig) -> list[dict]:
    p = _path(cfg)
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []


def add(cfg: AppConfig, story: Story, job_id: str) -> None:
    entries = load(cfg)
    entries.append({"at": datetime.now().isoformat(timespec="seconds"), "url": story.url, "title": story.title,
                    "source": story.source, "job": job_id})
    p = _path(cfg)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(entries[-500:], indent=1, ensure_ascii=False), encoding="utf-8")


def recent(cfg: AppConfig, days: int | None = None) -> list[dict]:
    days = cfg.news.repeat_window_days if days is None else days
    cutoff = datetime.now() - timedelta(days=days)
    out = []
    for e in load(cfg):
        try:
            if datetime.fromisoformat(e["at"]) >= cutoff:
                out.append(e)
        except (KeyError, ValueError):
            continue
    return out


def is_repeat(story: Story, covered: list[dict]) -> bool:
    for e in covered:
        if e.get("url") == story.url or fuzz.token_set_ratio(e.get("title", ""), story.title) >= SIMILAR:
            return True
    return False
