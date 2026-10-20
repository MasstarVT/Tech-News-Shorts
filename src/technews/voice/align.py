"""Word timings and take checks for engines that don't report phoneme durations (Chatterbox, ElevenLabs).

Chatterbox clips are force-aligned by a CTC model that only knows letters, so every caption token is spelled out
as plain words ("$5B" -> "five billion dollars"). The same words are compared with what the model heard to catch
takes that skip or garble words; number words must be heard exactly, because a wrong figure is a wrong fact.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field

import numpy as np

from .speech import SpeechToken, _split
from .timing import WordTime

_ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"]
_TENS = ["_", "_", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
_SCALES = ((10**12, "trillion"), (10**9, "billion"), (10**6, "million"), (1000, "thousand"))
_ORDINAL = {"one": "first", "two": "second", "three": "third", "five": "fifth", "eight": "eighth", "nine": "ninth",
            "twelve": "twelfth"}
_NUMBER_WORDS = {*_ONES, *_TENS[2:], "hundred", "thousand", "million", "billion", "trillion", "point", "percent",
                 "dollars", "dollar", "euros", "euro", "pounds", "pound", "times"}
_RE_PART = re.compile(r"(\d+)(st|nd|rd|th)\b|\d+(?:\.\d+)?|[a-z]+(?:'[a-z]+)*")


def int_words(n: int) -> str:
    if n < 20:
        return _ONES[n]
    if n < 100:
        return _TENS[n // 10] + (f" {_ONES[n % 10]}" if n % 10 else "")
    if n < 1000:
        return f"{_ONES[n // 100]} hundred" + (f" {int_words(n % 100)}" if n % 100 else "")
    for size, name in _SCALES:
        if n >= size:
            head, rest = divmod(n, size)
            return f"{int_words(head)} {name}" + (f" {int_words(rest)}" if rest else "")
    raise AssertionError(n)


def number_words(num: str) -> str:
    """'42' -> 'forty two', '3.5' -> 'three point five'. Absurdly long digit runs are read digit by digit."""
    whole, _, frac = num.replace(",", "").partition(".")
    if len(whole) > 15:
        head = " ".join(_ONES[int(d)] for d in whole)
    else:
        head = int_words(int(whole or "0"))
    if frac:
        head += " point " + " ".join(_ONES[int(d)] for d in frac)
    return head


def _ordinal(n: int) -> str:
    words = int_words(n).split()
    last = words[-1]
    if last in _ORDINAL:
        words[-1] = _ORDINAL[last]
    elif last.endswith("y"):
        words[-1] = last[:-1] + "ieth"
    else:
        words[-1] = last + "th"
    return " ".join(words)


def plain_words(spoken: str) -> list[str]:
    """Spoken text -> lowercase words of letters (and inner apostrophes), numbers spelled out."""
    text = spoken.lower().replace("’", "'").replace("%", " percent ").replace("&", " and ").replace("+", " plus ")
    text = re.sub(r"(?<=\d),(?=\d{3})", "", text)
    out: list[str] = []
    for m in _RE_PART.finditer(text):
        if m.group(1):
            out += _ordinal(int(m.group(1))).split()
        elif m.group(0)[0].isdigit():
            out += number_words(m.group(0)).split()
        else:
            out.append(m.group(0))
    return out


@dataclass
class Word:
    text: str
    token: int  # index into the scene's speech tokens
    weight: str  # "hard": must be heard exactly, "normal": counts toward the score, "soft": acronyms, short words


def expected_words(tokens: list[SpeechToken]) -> list[Word]:
    out: list[Word] = []
    sentence_start = True
    for i, tok in enumerate(tokens):
        core = _split(tok.text)[1]
        # Names (Nvidia, Qualcomm, RTX, iOS) are where recognisers stumble, not the voice: they don't count.
        name = sum(c.isupper() for c in core) >= 2 or (core[:1].isupper() and not sentence_start)
        sentence_start = tok.text.rstrip("\"”’')").endswith((".", "!", "?"))
        if not tok.spoken:
            continue
        numeric = any(c.isdigit() for c in tok.text)
        for w in plain_words(tok.spoken):
            if numeric and w in _NUMBER_WORDS:
                weight = "hard"
            elif name or len(w) <= 2:
                weight = "soft"
            else:
                weight = "normal"
            out.append(Word(w, i, weight))
    return out


@dataclass
class TakeCheck:
    score: float  # share of the normal and hard words that were heard
    missing: list[str] = field(default_factory=list)
    wrong_numbers: list[str] = field(default_factory=list)
    extra: int = 0  # heard words that aren't in the script (babble, repeats)
    ok: bool = True

    def summary(self) -> str:
        bits = [f"{self.score:.0%} of words heard"]
        if self.wrong_numbers:
            bits.append("numbers not heard: " + ", ".join(self.wrong_numbers))
        if self.missing:
            bits.append("missing: " + ", ".join(self.missing[:6]))
        if self.extra:
            bits.append(f"{self.extra} extra words")
        return "; ".join(bits)


def check_take(expected: list[Word], heard: str, min_score: float = 0.85) -> TakeCheck:
    """Compare the script's words with what the recogniser heard."""
    said = heard.split()
    want = [w.text for w in expected]
    matched = [False] * len(expected)
    extra = 0
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, want, said, autojunk=False).get_opcodes():
        if op == "equal":
            matched[i1:i2] = [True] * (i2 - i1)
        elif op == "insert":
            extra += j2 - j1
        elif op == "replace":
            block = set(said[j1:j2])
            close = difflib.SequenceMatcher(None, "".join(want[i1:i2]), "".join(said[j1:j2])).ratio() >= 0.75
            for k in range(i1, i2):
                # Misspellings ("nvidia" vs "invidia") are fine, a different number is not.
                matched[k] = want[k] in block or (close and expected[k].weight != "hard")
            if not close and any(w.weight != "soft" for w in expected[i1:i2]):
                extra += max(0, (j2 - j1) - (i2 - i1))  # spelled-out acronyms ("a o s p") aren't babble
    counted = [k for k, w in enumerate(expected) if w.weight != "soft"]
    score = sum(matched[k] for k in counted) / len(counted) if counted else 1.0
    missing = [expected[k].text for k in counted if not matched[k] and expected[k].weight == "normal"]
    wrong = [expected[k].text for k in counted if not matched[k] and expected[k].weight == "hard"]
    ok = not wrong and score >= min_score and extra <= max(3, len(expected) // 5)
    return TakeCheck(round(score, 3), missing, wrong, extra, ok)


def _close_gaps(words: list[WordTime], tokens: list[SpeechToken], end: float, max_gap: float = 0.3) -> list[WordTime]:
    """CTC and character timings end a word on its last letter's spike; hold it until the next spoken word starts."""
    out = []
    nxt = end
    for w, tok in zip(reversed(words), reversed(tokens), strict=True):
        if tok.spoken:
            stop = nxt if 0 <= nxt - w.end < max_gap else w.end
            out.append(WordTime(w.text, w.start, max(w.end, min(stop, end))))
            nxt = w.start
        else:
            out.append(w)
    return out[::-1]


def times_from_spans(tokens: list[SpeechToken], expected: list[Word], spans: list[list[float]], end: float) -> list[WordTime]:
    """Per-word [start, end, score] spans from the aligner -> one timing per speech token."""
    first: dict[int, float] = {}
    last: dict[int, float] = {}
    for w, span in zip(expected, spans, strict=False):
        a, b = span[0], span[1]
        if a < 0:
            continue
        first.setdefault(w.token, a)
        last[w.token] = max(b, last.get(w.token, b))
    return _fill(tokens, first, last, end)


def times_from_chars(tokens: list[SpeechToken], text: str, chars: list[str], starts: list[float], ends: list[float],
                     end: float) -> list[WordTime]:
    """ElevenLabs character timings for ``text`` (the tokens' spoken parts joined by spaces) -> token timings."""
    if "".join(chars) != text:
        # The service changed the text; line its characters up with ours where they agree.
        mapping = {}
        for a, b, size in difflib.SequenceMatcher(None, text, "".join(chars), autojunk=False).get_matching_blocks():
            for k in range(size):
                mapping[a + k] = b + k
    else:
        mapping = None
    first: dict[int, float] = {}
    last: dict[int, float] = {}
    pos = 0
    for i, tok in enumerate(tokens):
        if not tok.spoken:
            continue
        for c in range(pos, pos + len(tok.spoken)):
            j = c if mapping is None else mapping.get(c)
            if j is None or j >= len(starts) or text[c].isspace():
                continue
            first.setdefault(i, starts[j])
            last[i] = max(ends[j], last.get(i, ends[j]))
        pos += len(tok.spoken) + 1
    return _fill(tokens, first, last, end)


def _fill(tokens: list[SpeechToken], first: dict[int, float], last: dict[int, float], end: float) -> list[WordTime]:
    """Tokens the timings missed sit in the gap between their neighbours, split by length."""
    out: list[WordTime] = []
    k = 0
    prev_end = 0.0
    while k < len(tokens):
        if k in first:
            out.append(WordTime(tokens[k].text, first[k], last[k]))
            prev_end = last[k]
            k += 1
            continue
        run = k
        while run < len(tokens) and run not in first:
            run += 1
        nxt = first[run] if run < len(tokens) else end
        weights = [len(t.spoken) + 1 if t.spoken else 0 for t in tokens[k:run]]
        total = sum(weights) or 1
        acc = 0.0
        for t, wgt in zip(tokens[k:run], weights, strict=True):
            a = prev_end + (nxt - prev_end) * acc / total
            acc += wgt
            out.append(WordTime(t.text, a, prev_end + (nxt - prev_end) * acc / total))
        prev_end = nxt
        k = run
    return _close_gaps(out, tokens, end)


_RE_NUM = re.compile(r"(\d[\d,]*)(st|nd|rd|th)\b|\d[\d,]*(?:\.\d+)?")


def spell_out(spoken: str) -> str:
    """Numbers as words for engines that read digits unreliably: "50 90" -> "fifty ninety", "30%" -> "thirty percent"."""

    def num(m: re.Match) -> str:
        if m.group(1):
            return _ordinal(int(m.group(1).replace(",", "")))
        return number_words(m.group(0).rstrip(","))

    text = re.sub(r"(?<=\d)\s*%", " percent", spoken)
    return _RE_NUM.sub(num, text)


def speech_window(audio: np.ndarray, sr: int, first: float | None, last: float | None) -> tuple[int, int]:
    """Sample range to keep: the aligned words plus their natural decay, without lead-in breaths or tail babble."""
    hop = max(1, sr // 100)
    frames = max(1, len(audio) // hop)
    rms = np.sqrt(np.mean(audio[: frames * hop].reshape(frames, hop).astype(np.float64) ** 2, axis=1))
    loud = rms > (rms.max() or 1.0) * 10 ** (-35 / 20)
    dur = len(audio) / sr
    if first is None or last is None:
        voiced = np.flatnonzero(loud)
        if voiced.size == 0:
            return 0, len(audio)
        first, last = voiced[0] * hop / sr, (voiced[-1] + 1) * hop / sr
    start = max(0.0, first - 0.1)
    end = min(dur, last + 0.12)
    f = int(end * sr) // hop
    limit = min(frames, int((last + 0.45) * sr) // hop)
    while f < limit and loud[f]:  # let the last word's tail ring out, but stop before trailing noise
        f += 1
    end = max(end, min(dur, f * hop / sr + 0.03))
    return int(start * sr), int(end * sr)
