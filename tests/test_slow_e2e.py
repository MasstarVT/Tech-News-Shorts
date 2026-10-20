"""Full voice + render run. Needs the Kokoro model in data/models and `npm install` in video/.

Run with: RUN_SLOW=1 uv run pytest -m slow
"""

import os
import shutil

import pytest

from technews import pipeline
from technews.config import PROJECT_ROOT
from technews.jobs import Job
from technews.script import fallback
from technews.script.normalize import build_script

pytestmark = pytest.mark.slow

MODELS = PROJECT_ROOT / "data" / "models" / "kokoro"


@pytest.mark.skipif(os.environ.get("RUN_SLOW") != "1", reason="set RUN_SLOW=1")
def test_voice_and_render(cfg, story, tmp_path):
    if not (MODELS / "kokoro-v1.0.onnx").exists():
        pytest.skip("Kokoro model not downloaded")
    if not (PROJECT_ROOT / "video" / "node_modules").exists():
        pytest.skip("video/node_modules missing")
    (cfg.paths.data / "models").mkdir(parents=True)
    shutil.copytree(MODELS, cfg.paths.data / "models" / "kokoro")
    job = Job.create(cfg, story)
    job.save_script(build_script(fallback.draft(story), story, cfg, "null"))
    pipeline.stage_voice(job, cfg)
    track = job.load_voice()
    assert track.timed
    assert all(s.words and s.words[0].startMs >= 100 for s in track.scenes)
    pipeline.stage_render(job, cfg)
    assert job.video_path.stat().st_size > 100_000
