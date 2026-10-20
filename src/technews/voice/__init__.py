"""Voice stage: narrate every scene, time every word, measure mouth movement."""

from __future__ import annotations

import logging
import math
from collections.abc import Callable

import numpy as np
import soundfile as sf

from ..config import AppConfig
from ..jobs import Job
from ..models import SceneVoice, VoiceTrack, WordTiming
from .speech import spoken_text, to_speech
from .timing import estimate_word_timings, merge_silent, mouth_envelope, phoneme_groups, word_timings

log = logging.getLogger(__name__)

__all__ = ["synthesize_job"]


def synthesize_job(
    job: Job,
    cfg: AppConfig,
    voice: str | None = None,
    speed: float | None = None,
    progress: Callable[[int, int], None] | None = None,
    download_progress: Callable[[str, int, int], None] | None = None,
) -> VoiceTrack:
    from .kokoro import KokoroEngine

    script = job.load_script()
    voice = voice or cfg.voice.voice
    speed = speed or cfg.voice.speed
    fps = cfg.render.fps
    engine = KokoroEngine(cfg, download_progress)
    job.voice_dir.mkdir(exist_ok=True)

    scenes: list[SceneVoice] = []
    for i, scene in enumerate(script.scenes):
        tokens = to_speech(scene.narration, cfg.voice.pronunciations)
        text = spoken_text(tokens)
        if not text:
            raise ValueError(f"Scene {scene.id} has no narration to speak")
        audio, sr, timings = engine.synth(text, voice, speed)
        if engine.has_timings and timings:
            words = word_timings(tokens, phoneme_groups(timings), engine.phonemize)
        else:
            words = estimate_word_timings(tokens, len(audio) / sr)
        words = merge_silent(words, tokens)

        lead = int(cfg.voice.lead_in_s * sr)
        audio = np.concatenate([np.zeros(lead, dtype=np.float32), audio])
        last = i == len(script.scenes) - 1
        tail = cfg.voice.outro_tail_s if last else cfg.voice.scene_tail_s
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

    track = VoiceTrack(engine="kokoro", voice=voice, speed=speed, fps=fps, timed=engine.has_timings, scenes=scenes)
    job.save_voice(track)
    return track
