"""Turn narration into text the TTS reads well, keeping track of which caption word each spoken part belongs to.

espeak (Kokoro's phonemizer) reads "$5" as "dollar five" and "RTX 5090" as "five thousand ninety", so money,
multipliers, units and four-digit numbers are rewritten before synthesis. Captions keep the original words.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_LEAD = "\"“‘'([{"
_TRAIL = "\"”’'.,!?;:…)]}"
_KEEP_PUNCT = set(".,!?;:")

_CURRENCY = {"$": "dollars", "€": "euros", "£": "pounds"}
_CURRENCY_ONE = {"$": "dollar", "€": "euro", "£": "pound"}
_MAGNITUDE = {"k": "thousand", "m": "million", "mn": "million", "b": "billion", "bn": "billion", "t": "trillion"}
_MAGNITUDE_WORDS = {"thousand", "million", "billion", "trillion"}
_UNITS = {
    "hz": "hertz", "khz": "kilohertz", "mhz": "megahertz", "ghz": "gigahertz", "mah": "milliamp hours",
    "kwh": "kilowatt hours", "w": "watts", "kw": "kilowatts", "tb": "terabytes", "gb": "gigabytes",
    "mb": "megabytes", "nm": "nanometers", "mph": "miles per hour", "fps": "frames per second",
}

_RE_MONEY = re.compile(r"^([$€£])(\d[\d,]*(?:\.\d+)?)([kKmMbBtT][nN]?)?$")
_RE_TIMES = re.compile(r"^(\d+(?:\.\d+)?)[x×]$")  # lowercase only: "9950X" is a model name
_RE_UNIT = re.compile(r"^(\d+(?:\.\d+)?)([a-zA-Z]{1,3})$")
_RE_FOUR = re.compile(r"^(\d{4})([A-Za-z]{0,3})$")


@dataclass
class SpeechToken:
    text: str  # the caption word, as written
    spoken: str  # what the voice reads for it ("" = silent, e.g. a lone dash)


def _split(word: str) -> tuple[str, str, str]:
    i, j = 0, len(word)
    while i < j and word[i] in _LEAD:
        i += 1
    while j > i and word[j - 1] in _TRAIL:
        j -= 1
    return word[:i], word[i:j], word[j:]


def four_digits(n: int) -> str:
    """How people say four-digit numbers: 2026 -> "20 26", 5090 -> "50 90", 1500 -> "15 hundred"."""
    if n % 1000 == 0 or n % 100 < 10 and n % 100 != 0:
        return str(n)
    if n % 100 == 0:
        return f"{n // 100} hundred"
    return f"{n // 100} {n % 100}"


def _decimals(text: str) -> str:
    """espeak sometimes reads "3.5" as "three. five"; spell the point out."""
    return re.sub(r"(\d)\.(\d)", r"\1 point \2", text)


def _core_spoken(core: str, nxt: str | None, pron: dict[str, str]) -> tuple[str, str | None]:
    spoken, defer = _core_spoken_raw(core, nxt, pron)
    return _decimals(spoken), defer


def _core_spoken_raw(core: str, nxt: str | None, pron: dict[str, str]) -> tuple[str, str | None]:
    """Returns (spoken text, currency word to append after the *next* token or None)."""
    if not core:
        return "", None
    if core in pron:
        return pron[core], None
    for apostrophe in ("'s", "’s"):
        if core.endswith(apostrophe) and core[: -len(apostrophe)] in pron:
            return pron[core[: -len(apostrophe)]] + "'s", None
    if core == "&":
        return "and", None
    if m := _RE_MONEY.match(core):
        sym, num, mag = m.group(1), m.group(2), (m.group(3) or "").lower()
        if mag:
            return f"{num} {_MAGNITUDE.get(mag, mag)} {_CURRENCY[sym]}", None
        next_core = _split(nxt)[1].lower() if nxt else ""
        if next_core in _MAGNITUDE_WORDS:
            return num, _CURRENCY[sym]  # "$5 trillion" -> "5 trillion dollars"
        unit = _CURRENCY_ONE[sym] if num in ("1", "1.00") else _CURRENCY[sym]
        return f"{num} {unit}", None
    if m := _RE_TIMES.match(core):
        return f"{m.group(1)} times", None
    if m := _RE_FOUR.match(core):
        n, letters = int(m.group(1)), m.group(2)
        spoken = four_digits(n)
        return (f"{spoken} {letters}" if letters else spoken), None
    if m := _RE_UNIT.match(core):
        unit = _UNITS.get(m.group(2).lower())
        if unit:
            return f"{m.group(1)} {unit}", None
    return core, None


def to_speech(narration: str, pronunciations: dict[str, str] | None = None) -> list[SpeechToken]:
    pron = pronunciations or {}
    words = narration.split()
    tokens: list[SpeechToken] = []
    carry: str | None = None
    for i, word in enumerate(words):
        if word in pron:  # whole-word overrides such as "U.S." win over punctuation splitting
            spoken, defer = pron[word], None
            lead, trail = "", ""
        else:
            lead, core, trail = _split(word)
            spoken, defer = _core_spoken(core, words[i + 1] if i + 1 < len(words) else None, pron)
        if carry:
            spoken = f"{spoken} {carry}".strip()
            carry = None
        carry = defer
        punct = "".join(ch for ch in trail if ch in _KEEP_PUNCT)
        tokens.append(SpeechToken(text=word, spoken=f"{spoken}{punct}" if spoken else ""))
    if carry and tokens:
        tokens[-1].spoken = f"{tokens[-1].spoken} {carry}".strip()
    return tokens


def spoken_text(tokens: list[SpeechToken]) -> str:
    return " ".join(t.spoken for t in tokens if t.spoken)
