"""Word timings for captions and the mouth animation.

Kokoro reports when each phoneme is spoken. Phonemes are grouped into words at the spaces, then matched back to
the caption words: exactly when the per-word phonemization agrees with the sentence, proportionally otherwise.
"""

from __future__ import annotations

import bisect
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import NamedTuple

import numpy as np

from .speech import SpeechToken

_PUNCT = set(".,!?;:—–-…\"'()[]“”‘’ ")


@dataclass
class WordTime:
    text: str
    start: float  # seconds
    end: float


class Take(NamedTuple):
    """One scene as an engine spoke it."""

    audio: np.ndarray
    sr: int
    words: list[WordTime]  # one per speech token
    timed: bool  # False when the timings are estimates
    warnings: list[str]


@dataclass
class PhonemeGroup:
    phonemes: str
    start: float
    end: float


def _sounds(ph: str) -> str:
    return "".join(ch for ch in ph if ch not in _PUNCT)


def phoneme_groups(timings: Sequence) -> list[PhonemeGroup]:
    """Kokoro Timing objects (phoneme, start, end) -> one group per spoken word, punctuation dropped."""
    groups: list[PhonemeGroup] = []
    cur, start, end = "", 0.0, 0.0
    for t in [*timings, None]:
        if t is not None and t.phoneme != " ":
            if not cur:
                start = t.start
            cur += t.phoneme
            end = t.end
            continue
        if _sounds(cur):
            groups.append(PhonemeGroup(cur, start, end))
        cur = ""
    return groups


def _token_phonemes(tokens: list[SpeechToken], phonemize: Callable[[str], str]) -> list[list[str]]:
    out = []
    for tok in tokens:
        if not tok.spoken:
            out.append([])
            continue
        out.append([g for g in phonemize(tok.spoken).split() if _sounds(g)])
    return out


def word_timings(tokens: list[SpeechToken], groups: list[PhonemeGroup], phonemize: Callable[[str], str]) -> list[WordTime]:
    if not tokens:
        return []
    if not groups:
        return [WordTime(t.text, 0.0, 0.0) for t in tokens]
    per_token = _token_phonemes(tokens, phonemize)
    counts = [len(p) for p in per_token]
    out: list[WordTime] = []
    if sum(counts) == len(groups):
        k = 0
        last_end = groups[0].start
        for tok, n in zip(tokens, counts, strict=True):
            if n == 0:
                out.append(WordTime(tok.text, last_end, last_end))
                continue
            g0, g1 = groups[k], groups[k + n - 1]
            out.append(WordTime(tok.text, g0.start, g1.end))
            last_end = g1.end
            k += n
        return out
    return _proportional(tokens, per_token, groups)


def _proportional(tokens: list[SpeechToken], per_token: list[list[str]], groups: list[PhonemeGroup]) -> list[WordTime]:
    """Spread tokens over the spoken phonemes in proportion to their phoneme counts."""
    # Timeline of sounds: cumulative phoneme counts -> time, linear inside each group.
    lens = [max(1, len(_sounds(g.phonemes))) for g in groups]
    cum = np.concatenate([[0], np.cumsum(lens)]).astype(float)
    total = cum[-1]

    def at(pos: float, prefer_end: bool) -> float:
        pos = min(max(pos, 0.0), total)
        i = bisect.bisect_right(cum, pos) - 1
        if prefer_end and i > 0 and pos == cum[i]:
            i -= 1  # an end that lands on a boundary belongs to the group before it
        i = min(i, len(groups) - 1)
        g = groups[i]
        frac = (pos - cum[i]) / lens[i]
        return g.start + (g.end - g.start) * min(max(frac, 0.0), 1.0)

    tok_lens = [sum(len(_sounds(p)) for p in ph) for ph in per_token]
    tok_total = sum(tok_lens) or 1
    out: list[WordTime] = []
    acc = 0
    for tok, n in zip(tokens, tok_lens, strict=True):
        a = acc / tok_total * total
        acc += n
        b = acc / tok_total * total
        out.append(WordTime(tok.text, at(a, False), at(b, True) if n else at(a, False)))
    return out


def estimate_word_timings(tokens: list[SpeechToken], duration: float) -> list[WordTime]:
    """Fallback when the model reports no durations: spread words by length across the clip."""
    weights = [len(t.spoken) + 2 if t.spoken else 0 for t in tokens]
    total = sum(weights) or 1
    out, acc = [], 0.0
    for tok, w in zip(tokens, weights, strict=True):
        a = acc / total * duration
        acc += w
        out.append(WordTime(tok.text, a, acc / total * duration))
    return out


def merge_silent(words: list[WordTime], tokens: list[SpeechToken]) -> list[WordTime]:
    """Attach tokens that aren't spoken (a lone dash) to the neighbouring word so captions stay tidy."""
    out: list[WordTime] = []
    pending = ""
    for w, tok in zip(words, tokens, strict=True):
        if tok.spoken:
            text = f"{pending} {w.text}".strip() if pending else w.text
            out.append(WordTime(text, w.start, w.end))
            pending = ""
        elif out:
            out[-1] = WordTime(f"{out[-1].text} {w.text}", out[-1].start, out[-1].end)
        else:
            pending = f"{pending} {w.text}".strip()
    if pending and out:
        out[-1] = WordTime(f"{out[-1].text} {pending}", out[-1].start, out[-1].end)
    return out


def mouth_envelope(audio: np.ndarray, sr: int, fps: int, frames: int) -> list[float]:
    """Mouth openness per video frame from the narration loudness (0 closed .. 1 wide open)."""
    hop = sr / fps
    rms = np.zeros(frames, dtype=np.float32)
    for f in range(frames):
        seg = audio[int(f * hop) : int((f + 1) * hop)]
        if seg.size:
            rms[f] = float(np.sqrt(np.mean(np.square(seg, dtype=np.float64))))
    voiced = rms[rms > 1e-4]
    if voiced.size == 0:
        return [0.0] * frames
    ref = float(np.percentile(voiced, 95)) or 1.0
    v = np.clip(rms / ref, 0.0, 1.0)
    v[v < 0.12] = 0.0
    v = np.power(v, 0.8)
    return [round(float(x), 3) for x in v]
