"""Score candidate stories: fresh, widely covered, popular on Hacker News, on topics the channel cares about."""

from __future__ import annotations

import math
import re
from datetime import UTC, datetime

from rapidfuzz import fuzz

from ..config import AppConfig
from ..models import Story
from . import history

SAME_STORY = 68  # token_set_ratio between titles from different outlets


def _norm(title: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", title.lower())


def excluded(story: Story, cfg: AppConfig) -> bool:
    t = f" {story.title.lower()} "
    for kw in cfg.news.exclude_keywords:
        k = kw.lower()
        if (re.search(rf"(?<![a-z0-9]){re.escape(k)}(?![a-z0-9])", t) if k[0].isalnum() else k in t):
            return True
    return False


def cluster(stories: list[Story]) -> list[list[Story]]:
    """Group reports of the same news from different outlets."""
    groups: list[list[Story]] = []
    for s in stories:
        key = _norm(s.title)
        for g in groups:
            if any(fuzz.token_set_ratio(key, _norm(x.title)) >= SAME_STORY and x.source != s.source for x in g):
                g.append(s)
                break
        else:
            groups.append([s])
    return groups


def _weight(story: Story, cfg: AppConfig) -> float:
    for f in cfg.news.feeds:
        if f.name == story.source:
            return f.weight
    return cfg.news.hacker_news.weight if story.points else 1.0


def score(group: list[Story], cfg: AppConfig, now: datetime | None = None) -> Story:
    now = now or datetime.now(UTC)
    # Represent the group with the report carrying the most text.
    best = max(group, key=lambda s: (len(s.text or s.summary), _weight(s, cfg)))
    rep = best.model_copy(deep=True)
    rep.also_in = sorted({s.source for s in group if s.source != rep.source})
    rep.points = max(s.points for s in group)
    rep.comments = max(s.comments for s in group)
    rep.discussion_url = next((s.discussion_url for s in group if s.discussion_url), "")
    times = [s.published for s in group if s.published]
    rep.published = min(times) if times else None

    max_age = cfg.news.max_age_hours
    age_h = (now - rep.published).total_seconds() / 3600 if rep.published else max_age / 2
    recency = max(0.0, 1.0 - age_h / max_age)
    coverage = min(1.0, 0.35 * len(rep.also_in))
    hn = 0.4 * min(1.0, math.log10(rep.points) / 3) if rep.points > 1 else 0.0
    title = f" {rep.title.lower()} "
    kw = sum(boost for word, boost in cfg.news.boost_keywords.items() if re.search(rf"\b{re.escape(word.lower())}\b", title))
    rep.score = round((0.6 * recency + coverage + hn + min(kw, 0.6)) * _weight(rep, cfg), 4)
    return rep


def rank(stories: list[Story], cfg: AppConfig, now: datetime | None = None) -> list[Story]:
    now = now or datetime.now(UTC)
    covered = history.recent(cfg)
    fresh = []
    for s in stories:
        if excluded(s, cfg):
            continue
        if s.published and (now - s.published).total_seconds() / 3600 > cfg.news.max_age_hours:
            continue
        fresh.append(s)
    ranked = [score(g, cfg, now) for g in cluster(fresh)]
    ranked = [s for s in ranked if not history.is_repeat(s, covered)]
    return sorted(ranked, key=lambda s: s.score, reverse=True)
