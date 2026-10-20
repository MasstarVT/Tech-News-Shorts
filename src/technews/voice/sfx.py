"""Sound effects synthesized from scratch (no licensing questions): a paper swish and a rubber-stamp thud."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf

SR = 44100


def _normalize(x: np.ndarray, peak_db: float = -3.0) -> np.ndarray:
    peak = float(np.max(np.abs(x))) or 1.0
    return (x / peak * 10 ** (peak_db / 20)).astype(np.float32)


def _one_pole_lowpass(x: np.ndarray, cutoff: np.ndarray) -> np.ndarray:
    """Low-pass filter whose cutoff (Hz) can change every sample."""
    a = np.exp(-2 * np.pi * np.clip(cutoff, 20, SR / 2.2) / SR)
    y = np.empty_like(x)
    prev = 0.0
    for i in range(x.size):
        prev = (1 - a[i]) * x[i] + a[i] * prev
        y[i] = prev
    return y


def swish(duration: float = 0.42, seed: int = 7) -> np.ndarray:
    """Airy noise sweep, like a sheet of paper sliding past."""
    n = int(duration * SR)
    t = np.linspace(0, 1, n, endpoint=False)
    noise = np.random.default_rng(seed).standard_normal(n)
    cutoff = 400 + 5200 * np.sin(np.pi * t) ** 2  # opens up then closes
    low = _one_pole_lowpass(noise, cutoff)
    high = low - _one_pole_lowpass(low, np.full(n, 250.0))  # take out the rumble
    env = np.sin(np.pi * np.clip(t / 0.85, 0, 1)) ** 1.6
    return _normalize(high * env, -4.0)


def stamp(duration: float = 0.3, seed: int = 11) -> np.ndarray:
    """Short thump with a papery click on top."""
    n = int(duration * SR)
    t = np.arange(n) / SR
    freq = 70 + 90 * np.exp(-t * 40)
    phase = 2 * np.pi * np.cumsum(freq) / SR
    body = np.sin(phase) * np.exp(-t * 22)
    click = np.random.default_rng(seed).standard_normal(n) * np.exp(-t * 260) * 0.6
    click = _one_pole_lowpass(click, np.full(n, 3500.0))
    return _normalize(body + click, -3.0)


def write_sfx(folder: Path) -> dict[str, str]:
    """Write the effects into ``folder`` and return their paths relative to the job folder."""
    folder.mkdir(parents=True, exist_ok=True)
    out = {}
    for name, fn in (("swish", swish), ("stamp", stamp)):
        path = folder / f"{name}.wav"
        if not path.exists():
            sf.write(path, fn(), SR, subtype="PCM_16")
        out[name] = f"{folder.name}/{path.name}"
    return out
