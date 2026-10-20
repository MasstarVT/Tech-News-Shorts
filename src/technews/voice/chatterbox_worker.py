"""Chatterbox speech + word alignment, run inside the Chatterbox venv (see ``chatterbox.py``), never imported by the app.

Chatterbox reports no timings, so every clip is also run through a wav2vec2 CTC model: forced alignment of the
expected words gives each word's start and end, and a greedy decode of the same output says what was actually heard
(the app compares it with the script to catch skipped or garbled words).

Protocol: one JSON request per stdin line, one JSON reply per stdout line. The first reply is ``{"ready": ...}``.
  {"op": "speak", "text": str, "words": [str], "out": wav path, "seed": int, "voice": wav path | null,
   "exaggeration": float, "cfg_weight": float, "temperature": float}
  -> {"ok": true, "sr": int, "seconds": float, "spans": [[start_s, end_s, score], ...], "heard": str}
  {"op": "quit"}
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import traceback

# Anything the libraries print goes to stderr; the protocol owns the real stdout.
_proto = os.fdopen(os.dup(1), "w", encoding="utf-8", buffering=1)
os.dup2(2, 1)
sys.stdout = sys.stderr

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402
import torch  # noqa: E402
import torchaudio  # noqa: E402
import torchaudio.functional as F  # noqa: E402

ALIGN_SR = 16000


def reply(obj: dict) -> None:
    _proto.write(json.dumps(obj) + "\n")
    _proto.flush()


class Worker:
    def __init__(self, model: str, device: str):
        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = device
        if model == "turbo":
            from chatterbox.tts_turbo import ChatterboxTurboTTS

            self.tts = ChatterboxTurboTTS.from_pretrained(device=device)
        else:
            from chatterbox.tts import ChatterboxTTS

            self.tts = ChatterboxTTS.from_pretrained(device=device)
        self.turbo = model == "turbo"
        self.builtin = self.tts.conds
        bundle = torchaudio.pipelines.WAV2VEC2_ASR_LARGE_LV60K_960H
        self.aligner = bundle.get_model().to(device).eval()
        self.labels = bundle.get_labels()  # ('-', '|', 'E', 'T', ...): blank, word gap, letters, apostrophe
        self.index = {c: i for i, c in enumerate(self.labels)}
        self.voice: str | None = None

    def speak(self, req: dict) -> dict:
        seed = int(req.get("seed", 0))
        random.seed(seed)
        np.random.seed(seed % (2**32))
        torch.manual_seed(seed)
        voice = req.get("voice") or None
        kwargs = {"temperature": float(req.get("temperature", 0.8))}
        if not self.turbo:
            kwargs |= {"exaggeration": float(req.get("exaggeration", 0.5)), "cfg_weight": float(req.get("cfg_weight", 0.5))}
        if voice and voice != self.voice:
            kwargs["audio_prompt_path"] = voice  # conditionals are kept until the voice changes
        elif not voice and self.voice:
            self.tts.conds = self.builtin
        self.voice = voice
        with torch.inference_mode():
            wav = self.tts.generate(req["text"], **kwargs)
        audio = wav.squeeze(0).detach().cpu().numpy().astype(np.float32)
        sr = int(self.tts.sr)
        sf.write(req["out"], audio, sr, subtype="FLOAT")
        spans, heard = self.align(audio, sr, req.get("words") or [])
        return {"ok": True, "sr": sr, "seconds": round(len(audio) / sr, 3), "spans": spans, "heard": heard}

    def align(self, audio: np.ndarray, sr: int, words: list[str]) -> tuple[list[list[float]], str]:
        wave = torch.from_numpy(audio).unsqueeze(0)
        if sr != ALIGN_SR:
            wave = F.resample(wave, sr, ALIGN_SR)
        with torch.inference_mode():
            emission, _ = self.aligner(wave.to(self.device))
            emission = torch.log_softmax(emission, dim=-1).cpu()
        heard = self._greedy(emission[0])
        clean = ["".join(c for c in w.upper() if c in self.index and c not in "-|") for w in words]
        targets = [self.index[c] for w in clean for c in w]
        frames = emission.size(1)
        if not targets or len(targets) > frames:
            return [], heard
        aligned, scores = F.forced_align(emission, torch.tensor([targets], dtype=torch.int32), blank=0)
        token_spans = F.merge_tokens(aligned[0], scores[0].exp())
        sec = wave.size(1) / frames / ALIGN_SR
        spans: list[list[float]] = []
        k = 0
        for w in clean:
            if not w:
                spans.append([-1.0, -1.0, 0.0])
                continue
            part = token_spans[k : k + len(w)]
            k += len(w)
            score = sum(s.score * len(s) for s in part) / max(1, sum(len(s) for s in part))
            spans.append([round(part[0].start * sec, 3), round(part[-1].end * sec, 3), round(float(score), 3)])
        return spans, heard

    def _greedy(self, emission: torch.Tensor) -> str:
        ids = torch.unique_consecutive(emission.argmax(dim=-1)).tolist()
        text = "".join(self.labels[i] for i in ids if i != 0)
        return " ".join(text.replace("|", " ").split()).lower()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="standard", choices=["standard", "turbo"])
    ap.add_argument("--device", default="auto")
    args = ap.parse_args()
    try:
        worker = Worker(args.model, args.device)
    except Exception as e:
        reply({"ready": False, "error": f"{type(e).__name__}: {e}"})
        traceback.print_exc()
        return
    name = torch.cuda.get_device_name(0) if worker.device == "cuda" else "cpu"
    reply({"ready": True, "device": name})
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            req = json.loads(line)
            if req.get("op") == "quit":
                break
            reply(worker.speak(req))
        except Exception as e:
            traceback.print_exc()
            reply({"ok": False, "error": f"{type(e).__name__}: {e}"})


if __name__ == "__main__":
    main()
