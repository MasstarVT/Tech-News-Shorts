"""Chatterbox TTS on the GPU, in its own venv (it pins torch and numpy versions the app can't share).

``technews setup-chatterbox`` builds ``data/venvs/chatterbox`` with uv. Each voice run starts ``chatterbox_worker.py``
there once and sends it one line per scene. Every take is aligned and checked against the script; takes that skip
or garble words are re-recorded with a new seed, and the best take wins.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

import httpx
import soundfile as sf

from ..config import PROJECT_ROOT, AppConfig
from .align import check_take, expected_words, speech_window, spell_out, times_from_spans
from .master import stretch
from .speech import SpeechToken
from .timing import Take, estimate_word_timings

log = logging.getLogger(__name__)

VERSION = "0.1.7"
# chatterbox-tts pins torch 2.6, which has no kernels for RTX 50-series cards; 2.8 runs it fine. Gradio is only
# for its demo apps. setuptools<81 still ships pkg_resources, which the Perth watermarker imports.
OVERRIDES = 'torch==2.8.*\ntorchaudio==2.8.*\ngradio ; sys_platform == "never"\n'
WORKER = Path(__file__).with_name("chatterbox_worker.py")
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


def venv_dir(cfg: AppConfig) -> Path:
    return cfg.paths.data / "venvs" / "chatterbox"


def venv_python(cfg: AppConfig) -> Path:
    d = venv_dir(cfg)
    return d / "Scripts" / "python.exe" if sys.platform == "win32" else d / "bin" / "python"


def voices_dir(cfg: AppConfig) -> Path:
    return cfg.paths.data / "voices"


def reference_voices(cfg: AppConfig) -> list[str]:
    d = voices_dir(cfg)
    files = sorted(p.name for p in d.glob("*") if p.suffix.lower() in {".wav", ".mp3", ".flac"}) if d.exists() else []
    return ["default", *files]


def resolve_reference(cfg: AppConfig, voice: str) -> str | None:
    if not voice or voice == "default":
        return None
    for p in (voices_dir(cfg) / voice, Path(voice), PROJECT_ROOT / voice):
        if p.is_file():
            return str(p.resolve())
    raise ValueError(f"Chatterbox voice file '{voice}' not found (put clips in {voices_dir(cfg)})")


def setup(cfg: AppConfig, out: Callable[[str], None] = print) -> None:
    """Create the venv and install Chatterbox into it (a few GB with CUDA torch)."""
    uv = os.environ.get("UV") or shutil.which("uv")
    if not uv:
        raise RuntimeError("uv not found on PATH; install it from https://docs.astral.sh/uv/")
    py = venv_python(cfg)
    if not py.exists():
        out(f"Creating {venv_dir(cfg)}")
        subprocess.run([uv, "venv", str(venv_dir(cfg)), "--python", "3.12"], check=True, creationflags=_NO_WINDOW)
    with tempfile.TemporaryDirectory() as tmp:
        overrides = Path(tmp) / "overrides.txt"
        overrides.write_text(OVERRIDES, encoding="utf-8")
        out(f"Installing chatterbox-tts {VERSION} with torch for {cfg.voice.chatterbox.torch_backend}")
        subprocess.run([uv, "pip", "install", "--python", str(py), f"chatterbox-tts=={VERSION}", "setuptools<81",
                        "--override", str(overrides), "--torch-backend", cfg.voice.chatterbox.torch_backend],
                       check=True, creationflags=_NO_WINDOW)


def unload_ollama(cfg: AppConfig) -> None:
    """Ask Ollama to drop its loaded models so the GPU has room (it reloads them on the next request)."""
    prov = cfg.llm.providers.get("ollama")
    if not prov or not prov.base_url:
        return
    base = prov.base_url.rstrip("/")
    try:
        for m in httpx.get(f"{base}/api/ps", timeout=2).json().get("models", []):
            httpx.post(f"{base}/api/generate", json={"model": m["name"], "keep_alive": 0}, timeout=30)
            log.info("Unloaded %s from Ollama to free the GPU", m["name"])
    except (httpx.HTTPError, ValueError, KeyError):
        pass


class ChatterboxEngine:
    name = "chatterbox"

    def __init__(self, cfg: AppConfig, voice: str | None = None, speed: float | None = None):
        self.cfg = cfg
        self.cb = cfg.voice.chatterbox
        self.voice = voice or self.cb.voice
        self.speed = 1.0  # Chatterbox has no speed control; cfg_weight and exaggeration shape the pace
        self.reference = resolve_reference(cfg, self.voice)
        py = venv_python(cfg)
        if not py.exists():
            raise RuntimeError("Chatterbox isn't installed yet: run `technews setup-chatterbox`")
        if self.cb.unload_ollama and self.cb.device != "cpu":
            unload_ollama(cfg)
        models = cfg.paths.data / "models"
        env = dict(os.environ, HF_HOME=str(models / "huggingface"), TORCH_HOME=str(models / "torch"),
                   PYTHONIOENCODING="utf-8", HF_HUB_DISABLE_SYMLINKS_WARNING="1", PYTHONWARNINGS="ignore")
        self.tmp = Path(tempfile.mkdtemp(prefix="chatterbox-"))
        self.log_path = cfg.paths.data / "logs" / "chatterbox.log"
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._log = self.log_path.open("w", encoding="utf-8")
        self.proc = subprocess.Popen(
            [str(py), "-I", str(WORKER), "--model", self.cb.model, "--device", self.cb.device],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self._log, text=True, encoding="utf-8",
            env=env, creationflags=_NO_WINDOW,
        )
        ready = self._read()
        if not ready.get("ready"):
            self.close()
            raise RuntimeError(f"Chatterbox failed to start: {ready.get('error')} (see {self.log_path})")
        self.device = ready.get("device", "")
        log.info("Chatterbox %s ready on %s", self.cb.model, self.device)

    def _read(self) -> dict:
        line = self.proc.stdout.readline() if self.proc.stdout else ""
        if not line:
            self._log.flush()
            tail = self.log_path.read_text(encoding="utf-8", errors="replace").strip().splitlines()[-3:]
            raise RuntimeError("Chatterbox worker stopped: " + " | ".join(tail))
        return json.loads(line)

    def _call(self, req: dict) -> dict:
        assert self.proc.stdin
        self.proc.stdin.write(json.dumps(req) + "\n")
        self.proc.stdin.flush()
        reply = self._read()
        if not reply.get("ok"):
            raise RuntimeError(f"Chatterbox: {reply.get('error')} (see {self.log_path})")
        return reply

    def speak(self, tokens: list[SpeechToken], seed: int = 0, **_) -> Take:
        said = [SpeechToken(t.text, spell_out(t.spoken)) for t in tokens]
        text = " ".join(t.spoken for t in said if t.spoken)
        expected = expected_words(said)
        best = None
        for attempt in range(self.cb.retries + 1):
            out = self.tmp / f"take{attempt}.wav"
            r = self._call({
                "op": "speak", "text": text, "words": [w.text for w in expected], "out": str(out),
                "seed": seed + attempt * 7919, "voice": self.reference, "exaggeration": self.cb.exaggeration,
                "cfg_weight": self.cb.cfg_weight, "temperature": self.cb.temperature,
            })
            check = check_take(expected, r["heard"])
            log.info("chatterbox take %d: %s", attempt + 1, check.summary())
            if best is None or (check.ok, check.score) > (best[1].ok, best[1].score):
                audio, sr = sf.read(out, dtype="float32")
                best = (audio, check, r["spans"], int(sr))
            if check.ok:
                break
        audio, check, spans, sr = best
        valid = [s for s in spans if s[0] >= 0]
        a, b = speech_window(audio, sr, valid[0][0] if valid else None, valid[-1][1] if valid else None)
        pace = self.cb.effective_pace
        audio = stretch(audio[a:b], sr, pace)
        dur = len(audio) / sr
        shift = a / sr
        if valid:
            moved = [[(s[0] - shift) / pace, (s[1] - shift) / pace, s[2]] if s[0] >= 0 else s for s in spans]
            words = times_from_spans(tokens, expected, moved, dur)
        else:
            words = estimate_word_timings(tokens, dur)
        warnings = [] if check.ok else [f"voice take may be off ({check.summary()})"]
        return Take(audio, sr, words, bool(valid), warnings)

    def close(self) -> None:
        if self.proc.poll() is None:
            try:
                assert self.proc.stdin
                self.proc.stdin.write('{"op": "quit"}\n')
                self.proc.stdin.flush()
                self.proc.wait(timeout=20)
            except (OSError, subprocess.TimeoutExpired, AssertionError):
                self.proc.kill()
        self._log.close()
        shutil.rmtree(self.tmp, ignore_errors=True)
