"""A job is one video: a folder under out/ holding every stage's output.

out/2026-10-20_nvidia-passes-5-trillion/
  story.json     the picked story (+ article text)
  script.json    scenes, narration, on-screen visuals  <- edit this and re-run `voice` + `render`
  voice/         one wav per scene + timing.json (word timings, mouth movement)
  sfx/           generated sound effects
  props.json     what the Remotion video receives
  video.mp4      the finished short
  metadata.json  titles, descriptions and captions per platform
  job.json       stage status, publish results
  log.txt
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

from .config import AppConfig
from .models import Script, Story, VoiceTrack

log = logging.getLogger(__name__)


class JobState(BaseModel):
    id: str
    created: datetime
    status: str = "created"  # created | scripted | voiced | rendered | published | failed
    stages: dict[str, dict] = Field(default_factory=dict)
    published: dict[str, dict] = Field(default_factory=dict)


def slugify(text: str, max_len: int = 48) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    if len(text) > max_len:
        text = text[:max_len].rsplit("-", 1)[0]
    return text or "story"


def _write_json(path: Path, data) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    tmp.replace(path)


class Job:
    def __init__(self, folder: Path, cfg: AppConfig):
        self.dir = folder
        self.cfg = cfg

    # ------------------------------------------------------------------ create / open

    @classmethod
    def create(cls, cfg: AppConfig, story: Story) -> Job:
        root = cfg.paths.output
        root.mkdir(parents=True, exist_ok=True)
        base = f"{datetime.now():%Y-%m-%d}_{slugify(story.title)}"
        folder = root / base
        n = 2
        while folder.exists():
            folder = root / f"{base}-{n}"
            n += 1
        folder.mkdir(parents=True)
        job = cls(folder, cfg)
        job.save_state(JobState(id=folder.name, created=datetime.now()))
        job.save_story(story)
        return job

    @classmethod
    def open(cls, cfg: AppConfig, ref: str) -> Job:
        """``ref`` is a folder path, a folder name under out/, or "latest"."""
        root = cfg.paths.output
        if ref == "latest":
            jobs = sorted((p for p in root.glob("*/job.json")), key=lambda p: p.stat().st_mtime)
            if not jobs:
                raise FileNotFoundError(f"No jobs in {root} yet - run `technews make` first")
            return cls(jobs[-1].parent, cfg)
        p = Path(ref)
        for candidate in (p, root / ref):
            if (candidate / "job.json").exists():
                return cls(candidate.resolve(), cfg)
        matches = [q.parent for q in root.glob(f"*{ref}*/job.json")]
        if len(matches) == 1:
            return cls(matches[0], cfg)
        if matches:
            raise FileNotFoundError(f"'{ref}' matches several jobs: {', '.join(m.name for m in matches)}")
        raise FileNotFoundError(f"No job '{ref}' (looked in {root})")

    # ------------------------------------------------------------------ paths

    @property
    def id(self) -> str:
        return self.dir.name

    @property
    def video_path(self) -> Path:
        return self.dir / "video.mp4"

    @property
    def props_path(self) -> Path:
        return self.dir / "props.json"

    @property
    def voice_dir(self) -> Path:
        return self.dir / "voice"

    @property
    def log_path(self) -> Path:
        return self.dir / "log.txt"

    # ------------------------------------------------------------------ files

    def load_state(self) -> JobState:
        return JobState.model_validate_json((self.dir / "job.json").read_text(encoding="utf-8"))

    def save_state(self, state: JobState) -> None:
        _write_json(self.dir / "job.json", state.model_dump(mode="json"))

    def mark(self, stage: str, status: str | None = None, **info) -> None:
        state = self.load_state()
        state.stages[stage] = {"at": datetime.now().isoformat(timespec="seconds"), **info}
        if status:
            state.status = status
        self.save_state(state)

    def load_story(self) -> Story:
        return Story.model_validate_json((self.dir / "story.json").read_text(encoding="utf-8"))

    def save_story(self, story: Story) -> None:
        _write_json(self.dir / "story.json", story.model_dump(mode="json"))

    def has_script(self) -> bool:
        return (self.dir / "script.json").exists()

    def load_script(self) -> Script:
        return Script.model_validate_json((self.dir / "script.json").read_text(encoding="utf-8"))

    def save_script(self, script: Script) -> None:
        _write_json(self.dir / "script.json", script.model_dump(mode="json"))

    def has_voice(self) -> bool:
        return (self.voice_dir / "timing.json").exists()

    def load_voice(self) -> VoiceTrack:
        return VoiceTrack.model_validate_json((self.voice_dir / "timing.json").read_text(encoding="utf-8"))

    def save_voice(self, track: VoiceTrack) -> None:
        self.voice_dir.mkdir(exist_ok=True)
        _write_json(self.voice_dir / "timing.json", track.model_dump(mode="json"))

    def save_json(self, name: str, data) -> Path:
        path = self.dir / name
        _write_json(path, data)
        return path

    def load_json(self, name: str) -> dict:
        return json.loads((self.dir / name).read_text(encoding="utf-8"))

    # ------------------------------------------------------------------ logging

    def attach_log(self) -> logging.Handler:
        handler = logging.FileHandler(self.log_path, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s", "%H:%M:%S"))
        handler.setLevel(logging.INFO)
        logging.getLogger().addHandler(handler)
        return handler
