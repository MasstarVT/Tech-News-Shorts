"""Build the props the Remotion video receives (contract: video/src/types.ts)."""

from __future__ import annotations

import hashlib
import shutil
from datetime import datetime

from ..config import AppConfig
from ..jobs import Job
from ..voice.sfx import write_sfx

MUSIC_EXT = {".mp3", ".wav", ".ogg", ".m4a", ".aac"}


def _pick_music(job: Job, cfg: AppConfig) -> dict | None:
    folder = cfg.paths.resolve(cfg.render.music_dir)
    if not folder.is_dir():
        return None
    tracks = sorted(p for p in folder.iterdir() if p.suffix.lower() in MUSIC_EXT)
    if not tracks:
        return None
    # Same job -> same track, different jobs rotate through the folder.
    track = tracks[int(hashlib.sha1(job.id.encode()).hexdigest(), 16) % len(tracks)]
    dest = job.dir / "music" / track.name
    dest.parent.mkdir(exist_ok=True)
    if not dest.exists():
        shutil.copyfile(track, dest)
    return {"src": f"music/{track.name}", "volume": cfg.render.music_volume}


def build_props(job: Job, cfg: AppConfig) -> dict:
    script = job.load_script()
    voice = job.load_voice()
    story = job.load_story()
    by_id = {s.id: s for s in voice.scenes}
    missing = [s.id for s in script.scenes if s.id not in by_id]
    if missing:
        raise ValueError(f"Scenes {missing} have no narration yet - run `technews voice {job.id}`")

    scenes = []
    for s in script.scenes:
        v = by_id[s.id]
        scenes.append(
            {
                "id": s.id,
                "durationInFrames": v.frames,
                "audio": v.audio,
                "words": [w.model_dump() for w in v.words],
                "mouth": v.mouth,
                "visual": s.visual.to_props(),
            }
        )
    sfx = write_sfx(job.dir / "sfx") if cfg.render.sfx else {}
    date = story.published or datetime.now()
    props = {
        "brand": {"name": cfg.brand.name},
        "story": {"source": story.source, "date": f"{date:%b} {date.day}", "topic": script.topic},
        "theme": cfg.brand.theme,
        "scenes": scenes,
        "sfx": {"swish": sfx.get("swish"), "stamp": sfx.get("stamp")},
        "music": _pick_music(job, cfg),
        "captions": {
            "enabled": cfg.render.captions.enabled,
            "maxWords": cfg.render.captions.max_words,
            "maxChars": cfg.render.captions.max_chars,
        },
    }
    job.save_json("props.json", props)
    return props
