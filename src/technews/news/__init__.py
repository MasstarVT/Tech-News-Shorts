"""News stage: gather today's stories, rank them, pick one, fetch its article."""

from __future__ import annotations

from ..config import AppConfig
from ..models import Story
from .article import enrich, story_from_url
from .rank import rank
from .sources import fetch_all

__all__ = ["candidates", "enrich", "story_from_url"]


def candidates(cfg: AppConfig) -> list[Story]:
    """Ranked stories, best first, minus anything covered recently."""
    return rank(fetch_all(cfg), cfg)
