"""Script without an LLM (`provider: null`): built from the article's first sentences. Useful offline and for tests."""

from __future__ import annotations

import re

from ..models import Story
from .normalize import cap, short_phrase

_TOPICS = [
    ("AI", ["ai", "openai", "chatgpt", "anthropic", "claude", "gemini", "llm", "model", "copilot"]),
    ("Security", ["hack", "breach", "security", "malware", "ransomware", "vulnerability", "exploit"]),
    ("Gaming", ["game", "gaming", "xbox", "playstation", "nintendo", "steam", "console"]),
    ("Phones", ["iphone", "android", "pixel", "galaxy", "phone", "smartphone"]),
    ("Chips", ["chip", "nvidia", "amd", "intel", "gpu", "cpu", "semiconductor", "tsmc"]),
    ("Space", ["spacex", "nasa", "rocket", "satellite", "orbit", "starship"]),
    ("Cars", ["tesla", "ev", "electric vehicle", "self-driving", "waymo", "autonomous"]),
    ("Apple", ["apple", "mac", "ipad", "macos", "ios"]),
]

_ICON_HINTS = [
    ("ai", ["ai", "model", "chatbot", "openai", "llm"]), ("hack", ["hack", "breach", "attack", "malware"]),
    ("chip", ["chip", "gpu", "cpu", "processor", "semiconductor"]), ("phone", ["phone", "iphone", "android"]),
    ("money", ["$", "billion", "million", "price", "revenue", "funding", "deal"]), ("law", ["court", "lawsuit", "judge", "ruling"]),
    ("government", ["government", "regulator", "congress", "senate", "eu", "ftc"]), ("gamepad", ["game", "console"]),
    ("rocket", ["launch", "rocket", "spacex"]), ("car", ["car", "tesla", "vehicle"]), ("cloud", ["cloud", "server", "data center"]),
    ("people", ["users", "people", "customers", "employees"]), ("layoffs", ["layoff", "cuts jobs", "laid off"]),
]


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z\"“])", text.strip())
    return [p.strip() for p in parts if len(p.split()) >= 5]


def _find(table: list[tuple[str, list[str]]], text: str, default: str) -> str:
    low = f" {text.lower()} "
    for name, keys in table:
        if any(re.search(rf"(?<![a-z]){re.escape(k)}(?![a-z])", low) for k in keys):
            return name
    return default


def _trim_words(text: str, n: int) -> str:
    words = text.split()
    if len(words) <= n:
        return text
    return " ".join(words[:n]).rstrip(",;:") + "."


def draft(story: Story) -> dict:
    sentences = _sentences(story.context) or [story.title.rstrip(".") + "."]
    topic = _find(_TOPICS, f"{story.title} {story.context[:600]}", "Tech")
    hook = _trim_words(sentences[0], 28)
    scenes = [{"narration": hook, "visual": {"type": "headline", "text": short_phrase(story.title, 8)}}]
    for s in sentences[1:4]:
        s = _trim_words(s, 26)
        money = re.search(r"[$€£]\s?\d[\d,.]*\s?(?:billion|million|trillion|[BMKT])?|\d[\d.]*%", s)
        if money:
            visual = {"type": "stat", "value": money.group(0).replace(" ", ""), "label": short_phrase(s, 5)}
        else:
            visual = {"type": "icon", "icon": _find(_ICON_HINTS, s, "news"), "text": short_phrase(s, 5)}
        scenes.append({"narration": s, "visual": visual})
    return {
        "title": cap(story.title, 90),
        "topic": topic,
        "scenes": scenes,
        "outro": "That's the brief. See you tomorrow.",
        "description": cap(sentences[0], 200),
        "hashtags": ["tech", "technews", topic.lower()],
    }
