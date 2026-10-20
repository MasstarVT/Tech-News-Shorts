"""Fetch an article page and pull out its main text (used as the script writer's only source of facts)."""

from __future__ import annotations

import logging

import httpx

from ..config import AppConfig
from ..models import Story
from .sources import make_client, site_name, story_id

log = logging.getLogger(__name__)

MAX_CHARS = 7000


def extract_text(html: str, url: str = "") -> str:
    import trafilatura

    text = trafilatura.extract(
        html, url=url or None, include_comments=False, include_tables=False, favor_precision=True
    ) or ""
    return text.strip()[:MAX_CHARS]


def enrich(story: Story, cfg: AppConfig) -> Story:
    """Fill ``story.text`` from the article page unless the feed already carried the full text."""
    if story.text and len(story.text) > 1200:
        return story
    try:
        with make_client(cfg) as client:
            r = client.get(story.url)
            r.raise_for_status()
        text = extract_text(r.text, story.url)
    except (httpx.HTTPError, ValueError) as e:
        log.warning("Couldn't fetch the article (%s); using the feed summary", e)
        return story
    if len(text) > len(story.summary):
        story.text = text
    return story


def story_from_url(url: str, cfg: AppConfig) -> Story:
    """Build a story from any article link (for `technews make --url`)."""
    import trafilatura

    with make_client(cfg) as client:
        r = client.get(url)
        r.raise_for_status()
    meta = trafilatura.extract_metadata(r.text, default_url=url)
    title = (meta.title if meta and meta.title else "") or url
    source = (meta.sitename if meta and meta.sitename else "") or site_name(url)
    text = extract_text(r.text, url)
    return Story(id=story_id(url), title=title, url=url, source=source, summary=text[:600], text=text)
