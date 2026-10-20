import base64
import json
import random

import httpx
import numpy as np

from technews.config import VoiceConfig
from technews.jobs import Job
from technews.script import fallback
from technews.script.normalize import build_script
from technews.voice import elevenlabs, scene_pause, synthesize_job
from technews.voice.align import (
    check_take,
    expected_words,
    number_words,
    plain_words,
    speech_window,
    spell_out,
    times_from_chars,
    times_from_spans,
)
from technews.voice.kokoro import parse_blend
from technews.voice.master import loudness, master
from technews.voice.speech import SpeechToken, spoken_text, to_speech
from technews.voice.timing import Take, WordTime

PRON = VoiceConfig().pronunciations


def test_numbers_spelled_out():
    assert number_words("42") == "forty two"
    assert number_words("1,500") == "one thousand five hundred"
    assert number_words("3.05") == "three point zero five"
    assert number_words("2000000000") == "two billion"
    assert plain_words("50 90, 30% & the 3rd") == ["fifty", "ninety", "thirty", "percent", "and", "the", "third"]
    assert plain_words("year's M4") == ["year's", "m", "four"]
    assert spell_out("20 26 sales rose 30%, the 21st time.") == "twenty twenty six sales rose thirty percent, the twenty first time."


def test_expected_word_weights():
    tokens = to_speech("Nvidia sold $5B of RTX chips to Microsoft.", PRON)
    words = {w.text: w.weight for w in expected_words(tokens)}
    assert words["five"] == words["billion"] == words["dollars"] == "hard"
    assert words["nvidia"] == "normal"  # sentence start: could be any word
    assert words["rtx"] == words["microsoft"] == "soft"  # names: recognisers stumble on them
    assert words["chips"] == "normal" and words["of"] == "soft"


def test_check_take():
    exp = expected_words(to_speech("Nvidia sold $5B of chips to Microsoft this quarter.", PRON))
    good = check_take(exp, "and bidea sold five billion dollars of chips to micro soft this quarter")
    assert good.ok and good.missing == ["nvidia"]  # a misheard name opening the sentence costs a little
    wrong = check_take(exp, "nvidia sold five million dollars of chips to microsoft this quarter")
    assert not wrong.ok and wrong.wrong_numbers == ["billion"]
    skipped = check_take(exp, "nvidia sold five billion dollars to microsoft")
    assert not skipped.ok and "chips" in skipped.missing and "quarter" in skipped.missing
    acronyms = expected_words(to_speech("Apps using Google APIs run on AOSP-based ROMs like LineageOS.", PRON))
    spelled = check_take(acronyms, "apps using gougle a p ees run on a o s p based rhoms like lineage o s")
    assert spelled.ok and spelled.extra == 0
    babble = check_take(exp, "nvidia sold five billion dollars of chips to microsoft this quarter " + "uh " * 5)
    assert not babble.ok and babble.extra == 5


def test_times_from_spans_fills_unaligned_tokens():
    tokens = to_speech("Sales hit $5B — again.", PRON)
    exp = expected_words(tokens)
    assert [w.text for w in exp] == ["sales", "hit", "five", "billion", "dollars", "again"]
    spans = [[0.1, 0.4, 1], [0.5, 0.7, 1], [0.8, 1.0, 1], [-1, -1, 0], [1.3, 1.6, 1], [1.9, 2.3, 1]]
    words = times_from_spans(tokens, exp, spans, end=2.5)
    assert [w.text for w in words] == ["Sales", "hit", "$5B", "—", "again."]
    assert (words[2].start, words[2].end) == (0.8, 1.6)
    assert words[3].start == 1.6  # the silent dash sits after its neighbour (merge_silent folds it in)
    assert words[0].end == 0.5  # held until the next word starts
    assert words[-1].end == 2.5  # the last word rings out to the end of the clip


def test_times_from_chars():
    tokens = [SpeechToken("Hi", "Hi"), SpeechToken("—", ""), SpeechToken("there.", "there.")]
    text = spoken_text(tokens)
    chars = list(text)
    starts = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
    ends = [s + 0.1 for s in starts]
    words = times_from_chars(tokens, text, chars, starts, ends, end=1.0)
    assert (words[0].start, words[0].end, words[2].start, words[2].end) == (0.0, 0.3, 0.3, 1.0)  # last word held
    # the service may rewrite text; matching characters still carry the timings
    words = times_from_chars(tokens, text, list("Hi there!"), starts, ends, end=1.0)
    assert words[2].start == 0.3


def test_speech_window_trims_breath_and_babble():
    sr = 1000
    audio = np.zeros(3000, np.float32)
    audio[500:2000] = 0.5  # speech
    audio[2600:2700] = 0.5  # a stray noise after a pause
    a, b = speech_window(audio, sr, 0.5, 2.0)
    assert a == 400 and 2000 <= b < 2600


def test_master_levels_and_limits():
    sr = 24000
    t = np.arange(sr * 2) / sr
    quiet = (0.02 * np.sin(2 * np.pi * 220 * t) * (1 + np.sin(2 * np.pi * 3 * t))).astype(np.float32)
    out = master(quiet, sr, -16.0)
    assert abs(loudness(out, sr) - (-16.0)) < 1.0
    assert np.max(np.abs(out)) <= 10 ** (-1 / 20) + 1e-6
    assert master(np.zeros(10, np.float32), sr).size == 10


def test_scene_pause(cfg):
    rng = random.Random(1)
    flowing = scene_pause("and then,", 2, cfg, rng)
    stop = scene_pause("It ships today.", 2, cfg, random.Random(1))
    hook = scene_pause("It ships today.", 0, cfg, random.Random(1))
    assert flowing < stop < hook


def test_blend_and_engine_pronunciations():
    assert parse_blend("af_heart") == [("af_heart", 1.0)]
    assert parse_blend("af_heart:3+af_bella:1") == [("af_heart", 0.75), ("af_bella", 0.25)]
    v = VoiceConfig(pronunciations={"Asus": "ay-soos"})
    assert v.pronunciations_for("kokoro")["GPUs"] == "G P Use"
    assert "GPUs" not in v.pronunciations_for("elevenlabs")
    assert v.pronunciations_for("chatterbox")["Asus"] == "ay-soos"


def _pcm(seconds: float) -> str:
    samples = (np.sin(np.arange(int(24000 * seconds)) / 10) * 12000).astype("<i2")
    return base64.b64encode(samples.tobytes()).decode()


def test_elevenlabs_engine(cfg, monkeypatch, tmp_path):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        calls.append(body)
        if "previous_text" in body:
            return httpx.Response(400, json={"detail": {"message": "previous_text not supported"}})
        text = body["text"]
        step = 1.0 / len(text)
        return httpx.Response(200, json={
            "audio_base64": _pcm(1.0),
            "alignment": {"characters": list(text), "character_start_times_seconds": [i * step for i in range(len(text))],
                          "character_end_times_seconds": [(i + 1) * step for i in range(len(text))]},
        })

    monkeypatch.setattr(elevenlabs, "_client", lambda cfg: httpx.Client(base_url=elevenlabs.API,
                                                                       transport=httpx.MockTransport(handler)))
    engine = elevenlabs.ElevenLabsEngine(cfg, cache_dir=tmp_path / "cache")
    tokens = to_speech("RTX 5090 costs $2K.", PRON)
    take = engine.speak(tokens, seed=3, prev_text="Before.")
    assert take.timed and [w.text for w in take.words] == ["RTX", "5090", "costs", "$2K."]
    assert calls[0]["text"] == "RTX fifty ninety costs two thousand dollars."
    assert "previous_text" not in calls[1]  # refused once, retried without the neighbouring text
    assert all(a.start <= b.start for a, b in zip(take.words, take.words[1:], strict=False))
    engine.speak(tokens, seed=3)
    assert len(calls) == 2  # second time from the cache


class FakeEngine:
    voice, speed = "fake", 1.0

    def __init__(self):
        self.closed = False

    def speak(self, tokens, seed=0, **_):
        n = len(tokens)
        words = [WordTime(t.text, k * 0.3, k * 0.3 + 0.25) for k, t in enumerate(tokens)]
        return Take(np.full(int(24000 * 0.3 * n), 0.1, np.float32), 24000, words, True, ["clip may be off"])

    def close(self):
        self.closed = True


def test_synthesize_job_with_any_engine(cfg, story, monkeypatch):
    job = Job.create(cfg, story)
    job.save_script(build_script(fallback.draft(story), story, cfg, "null"))
    fake = FakeEngine()
    monkeypatch.setattr("technews.voice.open_engine", lambda *a, **k: fake)
    track = synthesize_job(job, cfg)
    assert fake.closed and track.voice == "fake" and track.timed
    assert len(track.warnings) == len(track.scenes) and track.warnings[0].startswith("Scene ")
    assert all(s.words[0].startMs == round(cfg.voice.lead_in_s * 1000) for s in track.scenes)
    assert (job.voice_dir / "s00.wav").exists()
