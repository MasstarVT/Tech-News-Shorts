"""Voice stage: narrate every scene, time every word, measure mouth movement."""

from __future__ import annotations

import logging
import math
import random
import zlib
from collections.abc import Callable
from pathlib import Path

import numpy as np
import soundfile as sf

from ..config import AppConfig
from ..jobs import Job
from ..models import SceneVoice, VoiceTrack, WordTiming
from .master import master
from .speech import spoken_text, to_speech
from .timing import merge_silent, mouth_envelope

log = logging.getLogger(__name__)

__all__ = ["open_engine", "synthesize_job", "scene_pause"]


def open_engine(cfg: AppConfig, voice: str | None = None, speed: float | None = None,
                download_progress: Callable[[str, int, int], None] | None = None, cache_dir: Path | None = None):
    """The configured engine. Each has ``voice``, ``speed``, ``speak(tokens, seed=, prev_text=, next_text=)``, ``close()``."""
    engine = cfg.voice.engine
    if engine == "chatterbox":
        from .chatterbox import ChatterboxEngine

        return ChatterboxEngine(cfg, voice, speed)
    if engine == "elevenlabs":
        from .elevenlabs import ElevenLabsEngine

        return ElevenLabsEngine(cfg, voice, speed, cache_dir=cache_dir)
    from .kokoro import KokoroEngine

    return KokoroEngine(cfg, download_progress, voice, speed)


def scene_pause(narration: str, index: int, cfg: AppConfig, rng: random.Random) -> float:
    """Silence after a scene: shorter when the sentence runs on, a beat more after the hook, never metronomic."""
    end = narration.rstrip().rstrip("\"”’')")
    base = cfg.voice.scene_tail_s
    if end.endswith((",", ";", ":", "—", "-")) or end[-1:].isalnum():
        base *= 0.5
    elif end.endswith(("?", "!")):
        base += 0.05
    if index == 0:
        base += cfg.voice.hook_pause_s
    return max(0.05, base + rng.uniform(-1, 1) * cfg.voice.pause_jitter_s)


def synthesize_job(
    job: Job,
    cfg: AppConfig,
    voice: str | None = None,
    speed: float | None = None,
    progress: Callable[[int, int], None] | None = None,
    download_progress: Callable[[str, int, int], None] | None = None,
) -> VoiceTrack:
    script = job.load_script()
    fps = cfg.render.fps
    pron = cfg.voice.pronunciations_for()
    rng = random.Random(zlib.crc32(job.id.encode()))
    engine = open_engine(cfg, voice, speed, download_progress, cache_dir=job.voice_dir / "cache")
    job.voice_dir.mkdir(exist_ok=True)

    scenes: list[SceneVoice] = []
    warnings: list[str] = []
    timed = True
    narrations = [s.narration for s in script.scenes]
    try:
        for i, scene in enumerate(script.scenes):
            tokens = to_speech(scene.narration, pron)
            if not spoken_text(tokens):
                raise ValueError(f"Scene {scene.id} has no narration to speak")
            take = engine.speak(
                tokens,
                seed=zlib.crc32(f"{job.id}:{i}".encode()),
                prev_text=spoken_text(to_speech(narrations[i - 1], pron)) if i else None,
                next_text=spoken_text(to_speech(narrations[i + 1], pron)) if i + 1 < len(narrations) else None,
            )
            sr = take.sr
            words = merge_silent(take.words, tokens)
            timed = timed and take.timed
            warnings += [f"Scene {scene.id}: {w}" for w in take.warnings]
            audio = master(take.audio, sr, cfg.voice.loudness_lufs) if cfg.voice.master else take.audio

            lead = int(cfg.voice.lead_in_s * sr)
            audio = np.concatenate([np.zeros(lead, dtype=np.float32), audio])
            last = i == len(script.scenes) - 1
            tail = cfg.voice.outro_tail_s if last else scene_pause(scene.narration, i, cfg, rng)
            duration = len(audio) / sr + tail
            frames = max(1, math.ceil(duration * fps))

            name = f"s{i:02d}.wav"
            sf.write(job.voice_dir / name, audio, sr, subtype="PCM_16")
            offset = cfg.voice.lead_in_s
            scenes.append(
                SceneVoice(
                    id=scene.id,
                    audio=f"voice/{name}",
                    duration_s=round(duration, 3),
                    frames=frames,
                    words=[
                        WordTiming(text=w.text, startMs=round((w.start + offset) * 1000), endMs=round((w.end + offset) * 1000))
                        for w in words
                    ],
                    mouth=mouth_envelope(audio, sr, fps, frames),
                )
            )
            log.info("voice %s: %.1fs, %d words", scene.id, duration, len(words))
            if progress:
                progress(i + 1, len(script.scenes))
    finally:
        engine.close()

    track = VoiceTrack(engine=cfg.voice.engine, voice=engine.voice, speed=engine.speed, fps=fps, timed=timed,
                       scenes=scenes, warnings=warnings)
    job.save_voice(track)
    return track
