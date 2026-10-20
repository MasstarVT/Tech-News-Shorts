"""Voice mastering, so every clip sounds like the same mic whichever engine spoke it.

High-pass the rumble, take a little mud out, lift presence, even out the level with a gentle compressor, then
bring the clip to a set loudness (BS.1770-style gated loudness, close enough to compare clips) under -1 dBFS.
"""

from __future__ import annotations

import numpy as np

CEILING_DB = -1.0


def _bell(f: np.ndarray, f0: float, gain_db: float, octaves: float) -> np.ndarray:
    x = np.log2(np.maximum(f, 1.0) / f0)
    return gain_db * np.exp(-0.5 * (x / octaves) ** 2)


def _filter(x: np.ndarray, sr: int, gain_db) -> np.ndarray:
    """Zero-phase FFT filter with a gain curve given as a function of frequency (Hz) -> dB."""
    pad = min(len(x), sr // 4)
    y = np.concatenate([np.zeros(pad, np.float32), x, np.zeros(pad, np.float32)])
    n = 1 << int(np.ceil(np.log2(len(y))))
    spec = np.fft.rfft(y, n)
    f = np.fft.rfftfreq(n, 1 / sr)
    spec *= 10 ** (gain_db(f) / 20)
    return np.fft.irfft(spec, n)[pad : pad + len(x)].astype(np.float32)


def _voice_eq(f: np.ndarray) -> np.ndarray:
    highpass = -10 * np.log10(1 + (80.0 / np.maximum(f, 1.0)) ** 4)  # 2nd-order 80 Hz
    return highpass + _bell(f, 300, -2.0, 0.6) + _bell(f, 3500, 2.0, 0.9)


def _k_weight(f: np.ndarray) -> np.ndarray:
    shelf = 10 * np.log10(1 + (10 ** 0.4 - 1) * f**2 / (f**2 + 1500.0**2))  # +4 dB above ~1.5 kHz
    return shelf - 10 * np.log10(1 + (38.0 / np.maximum(f, 1.0)) ** 4)


def loudness(x: np.ndarray, sr: int) -> float:
    """Gated integrated loudness in LUFS (-inf for silence)."""
    k = _filter(x, sr, _k_weight).astype(np.float64)
    block, hop = int(0.4 * sr), int(0.1 * sr)
    if len(k) < block:
        ms = np.array([np.mean(k**2)])
    else:
        ms = np.array([np.mean(k[i : i + block] ** 2) for i in range(0, len(k) - block + 1, hop)])
    lk = -0.691 + 10 * np.log10(np.maximum(ms, 1e-12))
    ms = ms[lk > -70]
    if ms.size == 0:
        return float("-inf")
    rel = -0.691 + 10 * np.log10(np.mean(ms)) - 10
    gated = ms[-0.691 + 10 * np.log10(ms) > rel]
    return float(-0.691 + 10 * np.log10(np.mean(gated if gated.size else ms)))


def _gain_to(x: np.ndarray, sr: int, target: float) -> np.ndarray:
    lufs = loudness(x, sr)
    return x if not np.isfinite(lufs) else (x * 10 ** ((target - lufs) / 20)).astype(np.float32)


def _compress(x: np.ndarray, sr: int, threshold_db: float, ratio: float = 2.5) -> np.ndarray:
    hop = max(1, sr // 200)  # 5 ms
    frames = int(np.ceil(len(x) / hop))
    padded = np.concatenate([x, np.zeros(frames * hop - len(x), np.float32)]).reshape(frames, hop)
    level = 10 * np.log10(np.maximum(np.mean(padded.astype(np.float64) ** 2, axis=1), 1e-12))
    want = -np.maximum(level - threshold_db, 0) * (1 - 1 / ratio)
    attack, release = np.exp(-1 / 2), np.exp(-1 / 16)  # ~10 ms / ~80 ms at 5 ms per frame
    gain = np.empty(frames)
    g = 0.0
    for i, w in enumerate(want):
        a = attack if w < g else release
        g = a * g + (1 - a) * w
        gain[i] = g
    per_sample = np.interp(np.arange(len(x)), np.arange(frames) * hop + hop / 2, gain)
    return (x * 10 ** (per_sample / 20)).astype(np.float32)


def master(audio: np.ndarray, sr: int, target_lufs: float = -16.0) -> np.ndarray:
    if audio.size < sr // 20 or not np.any(audio):
        return audio
    x = _filter(audio.astype(np.float32), sr, _voice_eq)
    x = _gain_to(x, sr, -20.0)
    x = _compress(x, sr, threshold_db=-24.0)
    x = _gain_to(x, sr, target_lufs)
    return _limit(x, sr, 10 ** (CEILING_DB / 20))


def _limit(x: np.ndarray, sr: int, ceiling: float) -> np.ndarray:
    """Peak limiter: dips the gain around each over-ceiling peak (~3 ms ramps) instead of turning the clip down."""
    need = np.minimum(1.0, ceiling / np.maximum(np.abs(x), 1e-9))
    if need.min() >= 1.0:
        return x.astype(np.float32)
    w = max(1, int(0.003 * sr))
    padded = np.pad(need, w, mode="edge")
    held = np.lib.stride_tricks.sliding_window_view(padded, 2 * w + 1).min(axis=1)  # hold the dip around the peak
    smooth = np.convolve(np.pad(held, w, mode="edge"), np.ones(w + 1) / (w + 1), mode="valid")[: len(x)]
    gain = np.minimum(smooth, held)
    return np.clip(x * gain, -ceiling, ceiling).astype(np.float32)


def stretch(x: np.ndarray, sr: int, pace: float, frame_ms: float = 30.0, search_ms: float = 8.0) -> np.ndarray:
    """Change the speaking pace without changing the pitch (WSOLA): pace 0.9 = 10% slower, 1.0 = untouched."""
    if abs(pace - 1.0) < 1e-3 or x.size < sr // 10:
        return x
    n = int(sr * frame_ms / 1000) // 2 * 2
    hop = n // 2
    tol = int(sr * search_ms / 1000)
    win = np.hanning(n).astype(np.float32)
    src = np.concatenate([np.zeros(tol + n, np.float32), x.astype(np.float32), np.zeros(tol + 2 * n, np.float32)])
    frames = int(len(x) / pace / hop) + 1
    out = np.zeros(frames * hop + n, np.float32)
    norm = np.zeros_like(out)
    pos = tol + n
    for k in range(frames):
        ideal = tol + n + int(k * hop * pace)
        if k:
            natural = src[pos + hop : pos + hop + n]  # what would have followed the previous frame
            region = src[ideal - tol : ideal + tol + n]
            pos = ideal - tol + int(np.argmax(np.correlate(region, natural, mode="valid")))
        else:
            pos = ideal
        out[k * hop : k * hop + n] += src[pos : pos + n] * win
        norm[k * hop : k * hop + n] += win
    out = out / np.maximum(norm, 1e-3)
    return out[: int(round(len(x) / pace))].astype(np.float32)
