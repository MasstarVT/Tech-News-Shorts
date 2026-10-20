"""Turn the writer's draft into a script the video can render, fixing what a small model tends to get wrong.

Also flags numbers that don't appear in the article (a cheap guard against made-up facts).
"""

from __future__ import annotations

import re

from ..config import AppConfig
from ..models import Script, ScriptScene, Story, Visual
from .schema import icon_names


class ScriptError(ValueError):
    pass


_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")


def clean(text: str | None) -> str:
    text = (text or "").replace("\n", " ").strip()
    text = re.sub(r"\s+", " ", text)
    return text.strip(" \"'“”")


def short_phrase(text: str, max_words: int = 6) -> str:
    words = clean(text).rstrip(".!?,;:").split()
    out = " ".join(words[:max_words])
    return out.rstrip(",;:")


def cap(text: str, max_chars: int) -> str:
    text = clean(text)
    if len(text) <= max_chars:
        return text
    cut = text[: max_chars + 1].rsplit(" ", 1)[0]
    return cut.rstrip(",;:-–—") or text[:max_chars]


def numbers(text: str) -> set[str]:
    out = set()
    for m in _NUM.findall(text or ""):
        n = m.replace(",", "").rstrip(".")
        if n.endswith(".0"):
            n = n[:-2]
        out.add(n)
    return out


def unverified_numbers(text: str, context: str, allow_single_digits: bool = True) -> list[str]:
    """Numbers in ``text`` that never appear in the article. Narration may use small counts ("two things",
    "M6") freely; stat graphics pass ``allow_single_digits=False`` because "$9B" must be backed by the article."""
    known = numbers(context)
    missing = []
    for n in sorted(numbers(text)):
        if n in known or (allow_single_digits and len(n) == 1 and n.isdigit()):
            continue
        missing.append(n)
    return missing


def _visual(raw: dict, narration: str, story: Story, cfg: AppConfig, warnings: list[str], first: bool, topic: str) -> Visual:
    t = raw.get("type") or "headline"
    text = clean(raw.get("text"))
    label = clean(raw.get("label"))
    fallback_text = text or label or short_phrase(narration, 7)

    def headline(txt: str) -> Visual:
        return Visual(type="headline", text=cap(txt or short_phrase(story.title, 8), 60), tag=cap(topic, 14) if first else "")

    if first or t == "headline":
        return headline(text if t == "headline" else short_phrase(story.title, 8))

    if t == "stat":
        value = re.sub(r"\s+", "", raw.get("value") or "")  # keep marks like 8.4" that clean() would strip
        if not re.search(r"\d", value):
            return headline(fallback_text)
        if cfg.script.verify_numbers:
            missing = unverified_numbers(value, story.context + " " + story.title, allow_single_digits=False)
            if missing:
                warnings.append(f"Stat '{value}' isn't in the article; shown as a headline instead")
                return headline(fallback_text)
        trend = raw.get("trend") if raw.get("trend") in ("up", "down") else "none"
        return Visual(type="stat", value=value[:9], label=cap(label or short_phrase(narration, 5), 40), trend=trend)

    if t == "icon":
        icon = clean(raw.get("icon")).lower()
        if icon not in icon_names():
            icon = "news"
        return Visual(type="icon", icon=icon, text=cap(text or short_phrase(narration, 6), 46))

    if t == "versus":
        left, right = cap(raw.get("left") or "", 22), cap(raw.get("right") or "", 22)
        if not left or not right:
            return headline(fallback_text)
        return Visual(type="versus", left=left, right=right, label=cap(label, 40))

    if t == "bullets":
        items = [cap(short_phrase(i, 6), 34) for i in (raw.get("items") or []) if clean(i)]
        if len(items) < 2:
            return headline(fallback_text)
        return Visual(type="bullets", items=items[:3])

    return headline(fallback_text)


def build_script(draft: dict, story: Story, cfg: AppConfig, llm: str) -> Script:
    warnings: list[str] = []
    topic = short_phrase(draft.get("topic") or "Tech", 2) or "Tech"
    scenes: list[ScriptScene] = []
    for raw in draft.get("scenes") or []:
        narration = clean(raw.get("narration"))
        if not narration:
            continue
        visual = _visual(raw.get("visual") or {}, narration, story, cfg, warnings, first=not scenes, topic=topic)
        scenes.append(ScriptScene(id=f"s{len(scenes):02d}", narration=narration, visual=visual))
    if not scenes:
        raise ScriptError("The writer returned no usable scenes")

    body = scenes[: cfg.script.max_scenes]
    outro_line = clean(draft.get("outro")) or "That's the brief. See you tomorrow."

    def words(items: list[ScriptScene]) -> int:
        return sum(len(s.narration.split()) for s in items) + len(outro_line.split())

    while words(body) > cfg.script.max_words and len(body) > cfg.script.min_scenes:
        body.pop(-1 if len(body) < 3 else -2)  # keep the hook and the last point, drop from the middle-end
    total = words(body)
    if total > cfg.script.max_words + 15:
        warnings.append(f"Narration is long ({total} words); the video may run past a minute")
    if total < cfg.script.min_words - 20:
        warnings.append(f"Narration is short ({total} words)")

    scenes = [s.model_copy(update={"id": f"s{i:02d}"}) for i, s in enumerate(body)]
    scenes.append(
        ScriptScene(id=f"s{len(scenes):02d}", narration=outro_line, visual=Visual(type="outro", text=cfg.brand.outro_text))
    )

    context = story.context + " " + story.title
    for s in scenes:
        missing = unverified_numbers(s.narration, context)
        if missing:
            warnings.append(f"Check {', '.join(missing)} in \"{cap(s.narration, 60)}\" - not found in the article")

    if len(story.context) < 300:
        warnings.append("Only a short summary was available for this story; check the facts")

    hashtags = []
    for h in draft.get("hashtags") or []:
        tag = re.sub(r"[^A-Za-z0-9_]", "", str(h).lstrip("#"))
        if tag and tag.lower() not in {x.lower() for x in hashtags}:
            hashtags.append(tag)
    return Script(
        title=cap(draft.get("title") or story.title, 90),
        topic=topic,
        description=clean(draft.get("description")),
        hashtags=hashtags[:6],
        scenes=scenes,
        llm=llm,
        warnings=warnings,
    )
