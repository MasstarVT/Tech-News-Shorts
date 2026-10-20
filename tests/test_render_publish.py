import re
from pathlib import Path

import pytest

from technews.config import PROJECT_ROOT
from technews.jobs import Job, slugify
from technews.models import SceneVoice, VoiceTrack, WordTiming
from technews.publish import _targets, build_metadata
from technews.publish.base import PostRequest
from technews.publish.export import export_job
from technews.publish.youtube import upload_body
from technews.render.props import build_props
from technews.script import fallback
from technews.script.normalize import build_script


@pytest.fixture
def job(cfg, story) -> Job:
    j = Job.create(cfg, story)
    script = build_script(fallback.draft(story), story, cfg, "null")
    j.save_script(script)
    scenes = [
        SceneVoice(id=s.id, audio=f"voice/s{i:02d}.wav", duration_s=2.0, frames=60,
                   words=[WordTiming(text=w, startMs=100 + k * 300, endMs=350 + k * 300) for k, w in enumerate(s.narration.split())],
                   mouth=[0.0] * 60)
        for i, s in enumerate(script.scenes)
    ]
    j.save_voice(VoiceTrack(engine="kokoro", voice="af_heart", speed=1.15, fps=30, timed=True, scenes=scenes))
    return j


def test_job_create_open_and_slug(cfg, story, job):
    assert job.dir.name.endswith(slugify(story.title))
    assert Job.open(cfg, "latest").dir == job.dir
    assert Job.open(cfg, job.id).dir == job.dir
    assert Job.open(cfg, "chipmaker").dir == job.dir
    second = Job.create(cfg, story)
    assert second.dir.name.endswith("-2")
    with pytest.raises(FileNotFoundError):
        Job.open(cfg, "chipmaker")  # now ambiguous


def test_props_follow_the_video_contract(cfg, job):
    (Path(cfg.render.music_dir)).mkdir(parents=True)
    (Path(cfg.render.music_dir) / "track.mp3").write_bytes(b"fake")
    props = build_props(job, cfg)
    assert set(props) == {"brand", "story", "theme", "scenes", "sfx", "music", "captions"}
    s0 = props["scenes"][0]
    assert set(s0) == {"id", "durationInFrames", "audio", "words", "mouth", "visual"}
    assert s0["visual"]["type"] == "headline" and s0["visual"]["tag"]
    assert props["scenes"][-1]["visual"] == {"type": "outro", "text": cfg.brand.outro_text}
    assert (job.dir / props["sfx"]["swish"]).exists() and (job.dir / props["sfx"]["stamp"]).exists()
    assert props["music"] == {"src": "music/track.mp3", "volume": cfg.render.music_volume}
    assert (job.dir / "props.json").exists()


def test_visual_types_match_typescript():
    ts = (PROJECT_ROOT / "video" / "src" / "types.ts").read_text(encoding="utf-8")
    ts_types = set(re.findall(r'\{type: "(\w+)"', ts))
    from technews.models import VisualType

    assert ts_types == set(VisualType.__args__)


def test_youtube_body_and_metadata(cfg, job):
    meta = build_metadata(job, cfg)
    assert job.load_story().url in meta["youtube"]["description"]
    body = upload_body(PostRequest(video=job.video_path, title="T" * 120, description="Desc", hashtags=["#tech", "ai"]))
    assert len(body["snippet"]["title"]) == 100
    assert body["snippet"]["description"].endswith("#tech #ai #Shorts")
    assert body["snippet"]["categoryId"] == "28"
    assert body["status"]["privacyStatus"] == "private"
    assert body["status"]["selfDeclaredMadeForKids"] is False


def test_export_and_targets(cfg, job):
    job.video_path.write_bytes(b"\x00" * 10)
    path = export_job(job, cfg, build_metadata(job, cfg))
    assert path.exists() and path.with_suffix(".txt").read_text(encoding="utf-8").startswith("YOUTUBE TITLE")
    assert [t.platform for t in _targets(cfg, None)] == ["export"]
    assert [t.platform for t in _targets(cfg, ["youtube"])] == ["youtube"]
