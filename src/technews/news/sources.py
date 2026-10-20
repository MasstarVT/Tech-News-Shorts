"""Fetch candidate stories from RSS/Atom feeds and the Hacker News front page."""

from __future__ import annotations

import hashlib
import html
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from urllib.parse import urljoin, urlparse

import feedparser
import httpx

from ..config import AppConfig, FeedConfig
from ..models import Story

log = logging.getLogger(__name__)

HN_API = "https://hacker-news.firebaseio.com/v0"

# Friendly names for links that come in through Hacker News.
KNOWN_SITES = {
    "theverge.com": "The Verge", "arstechnica.com": "Ars Technica", "techcrunch.com": "TechCrunch",
    "engadget.com": "Engadget", "wired.com": "Wired", "9to5mac.com": "9to5Mac", "9to5google.com": "9to5Google",
    "bloomberg.com": "Bloomberg", "reuters.com": "Reuters", "nytimes.com": "The New York Times",
    "theregister.com": "The Register", "tomshardware.com": "Tom's Hardware", "macrumors.com": "MacRumors",
    "github.com": "GitHub", "cnbc.com": "CNBC", "bbc.com": "BBC", "bbc.co.uk": "BBC", "zdnet.com": "ZDNET",
    "anandtech.com": "AnandTech", "wsj.com": "The Wall Street Journal", "ft.com": "Financial Times",
    "404media.co": "404 Media", "techradar.com": "TechRadar", "pcgamer.com": "PC Gamer", "ign.com": "IGN",
}


def story_id(url: str) -> str:
    return hashlib.sha1(url.strip().encode("utf-8")).hexdigest()[:12]


def site_name(url: str) -> str:
    host = urlparse(url).netloc.lower().removeprefix("www.")
    if host in KNOWN_SITES:
        return KNOWN_SITES[host]
    parts = host.split(".")
    base = ".".join(parts[-2:]) if len(parts) >= 2 else host
    return KNOWN_SITES.get(base, base)


def html_to_text(raw: str) -> str:
    if not raw:
        return ""
    try:
        import lxml.html

        text = lxml.html.fromstring(raw).text_content()
    except Exception:
        text = re.sub(r"<[^>]+>", " ", raw)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _entry_time(entry) -> datetime | None:
    for key in ("published_parsed", "updated_parsed", "created_parsed"):
        t = entry.get(key)
        if t:
            return datetime(*t[:6], tzinfo=UTC)
    return None


def parse_feed(content: bytes, feed: FeedConfig) -> list[Story]:
    parsed = feedparser.parse(content)
    stories = []
    for e in parsed.entries:
        link = e.get("link") or ""
        title = html_to_text(e.get("title") or "")
        if not link or not title:
            continue
        body = ""
        if e.get("content"):
            body = html_to_text(e["content"][0].get("value", ""))
        summary = html_to_text(e.get("summary") or "")
        stories.append(
            Story(
                id=story_id(link),
                title=title,
                url=link,
                source=feed.name,
                published=_entry_time(e),
                summary=summary[:1500],
                text=body if len(body) > len(summary) + 200 else "",
            )
        )
    return stories


def fetch_feed(client: httpx.Client, feed: FeedConfig) -> list[Story]:
    try:
        r = client.get(feed.url)
        r.raise_for_status()
    except httpx.HTTPError as e:
        log.warning("Feed %s failed: %s", feed.name, e)
        return []
    stories = parse_feed(r.content, feed)
    log.debug("%s: %d entries", feed.name, len(stories))
    return stories


def fetch_hacker_news(client: httpx.Client, cfg: AppConfig) -> list[Story]:
    hn = cfg.news.hacker_news
    try:
        ids = client.get(f"{HN_API}/topstories.json").json()[: max(hn.max_items * 2, 30)]
    except (httpx.HTTPError, ValueError) as e:
        log.warning("Hacker News failed: %s", e)
        return []

    def item(i: int) -> dict | None:
        try:
            return client.get(f"{HN_API}/item/{i}.json").json()
        except (httpx.HTTPError, ValueError):
            return None

    with ThreadPoolExecutor(max_workers=8) as pool:
        items = [x for x in pool.map(item, ids) if x]
    cutoff = datetime.now(UTC) - timedelta(hours=cfg.news.max_age_hours)
    stories = []
    for it in items:
        url = it.get("url")
        if it.get("type") != "story" or not url or it.get("score", 0) < hn.min_points:
            continue
        published = datetime.fromtimestamp(it.get("time", 0), tz=UTC)
        if published < cutoff:
            continue
        stories.append(
            Story(
                id=story_id(url),
                title=html_to_text(it.get("title", "")),
                url=url,
                source=site_name(url),
                published=published,
                points=int(it.get("score", 0)),
                comments=int(it.get("descendants", 0)),
                discussion_url=f"https://news.ycombinator.com/item?id={it.get('id')}",
            )
        )
        if len(stories) >= hn.max_items:
            break
    return stories


def make_client(cfg: AppConfig) -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": cfg.news.user_agent, "Accept": "*/*"},
        timeout=cfg.news.timeout_s,
        follow_redirects=True,
    )


FEED_TYPES = ("application/rss+xml", "application/atom+xml")
# Where sites usually keep a feed they don't advertise in their HTML.
COMMON_FEEDS = ("/feed/", "/rss/", "/feed.xml", "/rss.xml", "/atom.xml", "/index.xml")


def _alternate_feed(page: str, base: str) -> str:
    """The first feed a web page advertises with <link rel="alternate" type="application/rss+xml" href=...>."""
    for tag in re.findall(r"<link\b[^>]*>", page, re.I):
        attrs = {k.lower(): v for k, _, v in re.findall(r"([\w-]+)\s*=\s*([\"'])(.*?)\2", tag, re.S)}
        rels = attrs.get("rel", "").lower().split()
        if "alternate" in rels and attrs.get("type", "").lower() in FEED_TYPES and attrs.get("href"):
            return urljoin(base, html.unescape(attrs["href"]))
    return ""


def discover_feed(url: str, cfg: AppConfig) -> tuple[str, str, int]:
    """Find the feed behind ``url``: the feed itself, the one a site page links, or one at a usual path.
    Returns (feed url, feed title, entry count). Raises httpx.HTTPError, or ValueError when there's no feed."""
    with make_client(cfg) as client:
        r = client.get(url)
        r.raise_for_status()
        parsed = feedparser.parse(r.content)
        if not parsed.entries:
            page = str(r.url)
            link = _alternate_feed(r.text, page)
            for candidate in ([link] if link else []) + [urljoin(page, p) for p in COMMON_FEEDS]:
                try:
                    r = client.get(candidate)
                    r.raise_for_status()
                except httpx.HTTPError:
                    continue
                parsed = feedparser.parse(r.content)
                if parsed.entries:
                    url = candidate
                    break
            else:
                raise ValueError("No RSS or Atom feed found there. If the site has one, paste the feed's own link.")
    name = html_to_text(parsed.feed.get("title") or "") or site_name(url)
    return url, name[:60], len(parsed.entries)


def fetch_all(cfg: AppConfig) -> list[Story]:
    with make_client(cfg) as client:
        with ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(lambda f: fetch_feed(client, f), cfg.news.feeds))
        stories = [s for batch in results for s in batch]
        if cfg.news.hacker_news.enabled:
            stories += fetch_hacker_news(client, cfg)
    return stories
