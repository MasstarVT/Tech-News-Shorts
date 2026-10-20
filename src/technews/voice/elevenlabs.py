"""ElevenLabs text-to-speech over its HTTP API (paid per character, key in .env).

The with-timestamps endpoint returns each character's start and end, so captions and the mouth need no aligner.
Neighbouring scenes go along as previous_text/next_text so the delivery flows across cuts. Takes are cached by
text and settings in the job's voice folder: re-voicing after an edit only pays for the scenes that changed.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import re
from pathlib import Path

import httpx
import numpy as np

from ..config import AppConfig, secret
from .align import speech_window, spell_out, times_from_chars
from .speech import SpeechToken
from .timing import Take, WordTime, estimate_word_timings

log = logging.getLogger(__name__)

API = "https://api.elevenlabs.io"
SR = 24000
_RE_ID = re.compile(r"[A-Za-z0-9]{20}")


class ElevenLabsError(RuntimeError):
    pass


def _client(cfg: AppConfig) -> httpx.Client:
    key = secret(cfg.voice.elevenlabs.api_key_env)
    if not key:
        raise ElevenLabsError(f"Set {cfg.voice.elevenlabs.api_key_env} in .env to use ElevenLabs")
    return httpx.Client(base_url=API, headers={"xi-api-key": key}, timeout=httpx.Timeout(20, read=120))


def _raise_for(r: httpx.Response) -> None:
    if r.is_success:
        return
    try:
        detail = r.json().get("detail")
        msg = detail.get("message") if isinstance(detail, dict) else detail
    except ValueError:
        msg = r.text[:200]
    hint = {401: " (check the API key)", 404: " (run `technews voices` for valid voices)"}.get(r.status_code, "")
    raise ElevenLabsError(f"ElevenLabs {r.status_code}: {msg}{hint}")


def list_voices(cfg: AppConfig) -> list[dict]:
    """The account's voices: [{"name", "voice_id", "category"}]."""
    with _client(cfg) as c:
        r = c.get("/v1/voices")
        _raise_for(r)
        return [{"name": v["name"], "voice_id": v["voice_id"], "category": v.get("category", "")}
                for v in r.json().get("voices", [])]


def resolve_voice(cfg: AppConfig, voice: str) -> str:
    if _RE_ID.fullmatch(voice):
        return voice
    for v in list_voices(cfg):
        if v["name"].lower() == voice.lower() or v["name"].split(" - ")[0].lower() == voice.lower():
            return v["voice_id"]
    raise ElevenLabsError(f"No ElevenLabs voice named '{voice}' (run `technews voices`)")


class ElevenLabsEngine:
    name = "elevenlabs"

    def __init__(self, cfg: AppConfig, voice: str | None = None, speed: float | None = None,
                 cache_dir: Path | None = None):
        self.el = cfg.voice.elevenlabs
        self.voice = voice or self.el.voice
        self.speed = min(1.2, max(0.7, speed or self.el.speed))
        self.client = _client(cfg)
        self.voice_id = resolve_voice(cfg, self.voice)
        self.cache_dir = cache_dir

    def _settings(self) -> dict:
        return {"stability": self.el.stability, "similarity_boost": self.el.similarity_boost, "style": self.el.style,
                "use_speaker_boost": True, "speed": self.speed}

    def _cache_key(self, text: str) -> str:
        raw = json.dumps([self.voice_id, self.el.model, self._settings(), text], sort_keys=True)
        return hashlib.sha1(raw.encode()).hexdigest()[:16]

    def _request(self, text: str, seed: int, prev_text: str | None, next_text: str | None) -> dict:
        body: dict = {"text": text, "model_id": self.el.model, "voice_settings": self._settings(), "seed": seed}
        if self.el.stitch:
            body |= {k: v for k, v in (("previous_text", prev_text), ("next_text", next_text)) if v}
        url = f"/v1/text-to-speech/{self.voice_id}/with-timestamps"
        r = self.client.post(url, params={"output_format": f"pcm_{SR}"}, json=body)
        if r.status_code in (400, 422) and ("previous_text" in body or "next_text" in body):
            log.info("ElevenLabs refused the neighbouring text for %s; retrying without it", self.el.model)
            body.pop("previous_text", None)
            body.pop("next_text", None)
            r = self.client.post(url, params={"output_format": f"pcm_{SR}"}, json=body)
        _raise_for(r)
        return r.json()

    def speak(self, tokens: list[SpeechToken], seed: int = 0, prev_text: str | None = None,
              next_text: str | None = None) -> Take:
        said = [SpeechToken(t.text, spell_out(t.spoken)) for t in tokens]
        text = " ".join(t.spoken for t in said if t.spoken)
        cached = self.cache_dir / f"{self._cache_key(text)}.json" if self.cache_dir else None
        if cached and cached.exists():
            data = json.loads(cached.read_text(encoding="utf-8"))
        else:
            data = self._request(text, seed % 4_294_967_295, prev_text and spell_out(prev_text),
                                 next_text and spell_out(next_text))
            if cached:
                cached.parent.mkdir(parents=True, exist_ok=True)
                cached.write_text(json.dumps(data), encoding="utf-8")
        audio = np.frombuffer(base64.b64decode(data["audio_base64"]), dtype="<i2").astype(np.float32) / 32768
        al = data.get("alignment") or {}
        chars, starts, ends = al.get("characters"), al.get("character_start_times_seconds"), al.get("character_end_times_seconds")
        timed = bool(chars and starts and ends)
        first = last = None
        if timed:
            words = times_from_chars(said, text, chars, starts, ends, len(audio) / SR)
            spoken = [w for w, t in zip(words, said, strict=True) if t.spoken]
            if spoken:
                first, last = spoken[0].start, spoken[-1].end
        a, b = speech_window(audio, SR, first, last)
        audio = audio[a:b]
        dur, shift = len(audio) / SR, a / SR
        if timed:
            words = [WordTime(t.text, max(0.0, w.start - shift), min(dur, max(0.0, w.end - shift)))
                     for w, t in zip(words, tokens, strict=True)]
        else:
            words = estimate_word_timings(tokens, dur)
        return Take(audio, SR, words, timed, [])

    def close(self) -> None:
        self.client.close()
