"""Kokoro TTS (kokoro-onnx, runs on the CPU). Model files are downloaded on first use (~350 MB)."""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

import httpx
import numpy as np

from ..config import AppConfig
from .speech import SpeechToken, spoken_text
from .timing import Take, estimate_word_timings, phoneme_groups, word_timings

log = logging.getLogger(__name__)


def model_paths(cfg: AppConfig) -> tuple[Path, Path]:
    d = cfg.paths.data / "models" / "kokoro"
    return d / Path(cfg.voice.model_url).name, d / Path(cfg.voice.voices_url).name


def _download(url: str, dest: Path, progress: Callable[[str, int, int], None] | None = None) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    log.info("Downloading %s", url)
    with httpx.stream("GET", url, follow_redirects=True, timeout=httpx.Timeout(60, read=300)) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        done = 0
        with tmp.open("wb") as fh:
            for chunk in r.iter_bytes(1 << 20):
                fh.write(chunk)
                done += len(chunk)
                if progress:
                    progress(dest.name, done, total)
    tmp.replace(dest)


def ensure_model_files(cfg: AppConfig, progress: Callable[[str, int, int], None] | None = None) -> tuple[Path, Path]:
    model, voices = model_paths(cfg)
    for url, path in ((cfg.voice.model_url, model), (cfg.voice.voices_url, voices)):
        if not path.exists() or path.stat().st_size < 1_000_000:
            _download(url, path, progress)
    return model, voices


def parse_blend(voice: str) -> list[tuple[str, float]]:
    """"af_heart:0.7+af_bella:0.3" -> [("af_heart", 0.7), ("af_bella", 0.3)]; weights default to equal shares."""
    parts = []
    for part in voice.split("+"):
        name, _, weight = part.strip().partition(":")
        parts.append((name.strip(), float(weight) if weight else 1.0))
    total = sum(w for _, w in parts)
    if not parts or total <= 0:
        raise ValueError(f"Bad voice blend '{voice}'")
    return [(n, w / total) for n, w in parts]


class KokoroEngine:
    name = "kokoro"

    def __init__(self, cfg: AppConfig, progress: Callable[[str, int, int], None] | None = None,
                 voice: str | None = None, speed: float | None = None):
        from kokoro_onnx import Kokoro

        model, voices = ensure_model_files(cfg, progress)
        self.cfg = cfg
        self.voice = voice or cfg.voice.voice
        self.speed = speed or cfg.voice.speed
        self.kokoro = Kokoro(str(model), str(voices))
        self.sample_rate = 24000
        if not self.kokoro.has_timings:
            log.warning("This Kokoro model reports no phoneme durations; caption timing will be estimated")

    @property
    def has_timings(self) -> bool:
        return bool(self.kokoro.has_timings)

    def voices(self) -> list[str]:
        return self.kokoro.get_voices()

    def phonemize(self, text: str) -> str:
        return self.kokoro.tokenizer.phonemize(text, self.cfg.voice.lang)

    def style(self, voice: str) -> np.ndarray:
        blend = parse_blend(voice)
        for name, _ in blend:
            if name not in self.kokoro.voices:
                raise ValueError(f"Unknown Kokoro voice '{name}'. Run `technews voices` to list them.")
        return sum(self.kokoro.get_voice_style(n) * w for n, w in blend).astype(np.float32)

    def synth(self, text: str, voice: str, speed: float) -> tuple[np.ndarray, int, list]:
        style = self.style(voice)
        audio, sr, timings = self.kokoro.create_timed(text, voice=style, speed=speed, lang=self.cfg.voice.lang)
        self.sample_rate = sr
        return np.asarray(audio, dtype=np.float32), sr, timings

    def speak(self, tokens: list[SpeechToken], **_) -> Take:
        audio, sr, timings = self.synth(spoken_text(tokens), self.voice, self.speed)
        if self.has_timings and timings:
            return Take(audio, sr, word_timings(tokens, phoneme_groups(timings), self.phonemize), True, [])
        return Take(audio, sr, estimate_word_timings(tokens, len(audio) / sr), False, [])

    def close(self) -> None:
        pass
