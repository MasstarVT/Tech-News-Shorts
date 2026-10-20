from dataclasses import dataclass

import numpy as np

from technews.voice.speech import SpeechToken
from technews.voice.timing import (
    estimate_word_timings,
    merge_silent,
    mouth_envelope,
    phoneme_groups,
    word_timings,
)


@dataclass
class T:
    phoneme: str
    start: float
    end: float


def timings(words: list[tuple[str, float, float]]) -> list[T]:
    """Build per-phoneme timings: each word's phonemes share its span evenly, spaces between words."""
    out = []
    for i, (ph, s, e) in enumerate(words):
        step = (e - s) / len(ph)
        out += [T(c, s + k * step, s + (k + 1) * step) for k, c in enumerate(ph)]
        if i < len(words) - 1:
            out.append(T(" ", e, words[i + 1][1]))
    return out


FAKE_PHONEMES = {"five": "faɪv", "trillion": "tɹɪljən", "dollars": "dɑlɚz", "Nvidia": "ɛnvɪdiə", "passed": "pæst"}


def phonemize(text: str) -> str:
    return " ".join(FAKE_PHONEMES.get(w.strip(".,"), w) for w in text.split())


def test_groups_drop_punctuation_only_groups():
    groups = phoneme_groups(timings([("ab", 0.0, 0.2), ("—", 0.25, 0.3), ("cd,", 0.4, 0.6)]))
    assert [g.phonemes for g in groups] == ["ab", "cd,"]


def test_exact_mapping_when_counts_match():
    toks = [SpeechToken("Nvidia", "Nvidia"), SpeechToken("passed", "passed"), SpeechToken("$5", "five"),
            SpeechToken("trillion.", "trillion dollars.")]
    groups = phoneme_groups(timings([("ɛnvɪdiə", 0.0, 0.5), ("pæst", 0.55, 0.8), ("faɪv", 0.9, 1.1),
                                     ("tɹɪljən", 1.2, 1.5), ("dɑlɚz.", 1.55, 1.9)]))
    words = word_timings(toks, groups, phonemize)
    assert [(w.text, round(w.start, 2), round(w.end, 2)) for w in words] == [
        ("Nvidia", 0.0, 0.5), ("passed", 0.55, 0.8), ("$5", 0.9, 1.1), ("trillion.", 1.2, 1.9)]


def test_proportional_mapping_when_counts_disagree():
    toks = [SpeechToken("one", "aaaa"), SpeechToken("two", "bbbb")]
    # The sentence was phonemized as one group, the words separately as two.
    groups = phoneme_groups(timings([("aaaabbbb", 0.0, 1.0)]))
    words = word_timings(toks, groups, lambda t: t)
    assert round(words[0].start, 2) == 0.0
    assert round(words[0].end, 2) == 0.5
    assert round(words[1].start, 2) == 0.5
    assert round(words[1].end, 2) == 1.0


def test_estimate_and_merge_silent():
    toks = [SpeechToken("Fast", "Fast"), SpeechToken("—", ""), SpeechToken("really", "really")]
    words = estimate_word_timings(toks, 1.0)
    merged = merge_silent(words, toks)
    assert [w.text for w in merged] == ["Fast —", "really"]
    assert merged[-1].end == 1.0


def test_mouth_envelope_opens_on_loud_frames():
    sr, fps = 24000, 30
    audio = np.zeros(sr, dtype=np.float32)
    audio[sr // 2 :] = 0.5 * np.sin(np.linspace(0, 2000, sr // 2))
    env = mouth_envelope(audio, sr, fps, fps)
    assert max(env[:10]) == 0.0
    assert min(env[20:]) > 0.5
