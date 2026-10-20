"""Web app API, offline: a temporary config and out/ folder, no worker threads."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from technews.config import load_config  # noqa: E402
from technews.jobs import Job  # noqa: E402
from technews.models import Script, ScriptScene, Visual  # noqa: E402
from technews.web.app import create_app  # noqa: E402
from technews.web.auto import AutoScheduler, AutoSettings, AutoState, AutoStore, due  # noqa: E402
from technews.web.settings import update_config  # noqa: E402

CONFIG = """\
# Test config
paths:
  data_dir: {tmp}/data
  output_dir: {tmp}/out
voice:
  speed: 1.15        # keep this comment
"""


@pytest.fixture
def env(tmp_path: Path, monkeypatch, story):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(CONFIG.format(tmp=tmp_path.as_posix()), encoding="utf-8")
    monkeypatch.setenv("TECHNEWS_CONFIG", str(cfg_file))
    load_config.cache_clear()
    cfg = load_config()
    job = Job.create(cfg, story)
    job.save_script(
        Script(
            title="Faster laptop chip",
            topic="Chips",
            description="A new chip.",
            scenes=[
                ScriptScene(id="s00", narration="A new laptop chip is 30% faster.", visual=Visual(type="headline", text="Faster chip")),
                ScriptScene(id="s01", narration="It costs $499 for laptop makers.", visual=Visual(type="stat", value="$499", label="price")),
                ScriptScene(id="s02", narration="See you tomorrow.", visual=Visual(type="outro", text="Follow")),
            ],
        )
    )
    yield cfg, job, cfg_file
    load_config.cache_clear()


def _body(job: Job, **stat) -> dict:
    s = job.load_script()
    scenes = [{"narration": x.narration, "visual": x.visual.model_dump()} for x in s.scenes]
    scenes[1]["visual"].update(stat)
    return {"title": s.title, "topic": s.topic, "description": s.description, "hashtags": ["#Chips", "chips"], "scenes": scenes}


def test_jobs_list_and_detail(env):
    _, job, _ = env
    c = TestClient(create_app(background=False))
    jobs = c.get("/api/jobs").json()
    assert [j["id"] for j in jobs] == [job.id]
    assert jobs[0]["stale"] == {"voice": False, "render": False}
    d = c.get(f"/api/jobs/{job.id}").json()
    assert d["script"]["scenes"][1]["visual"]["value"] == "$499"
    assert d["voice"] is None and d["videos"] == []


def test_saving_a_script_rechecks_facts(env):
    _, job, _ = env
    c = TestClient(create_app(background=False))
    res = c.put(f"/api/jobs/{job.id}/script", json=_body(job, value="$9B"))
    assert res.status_code == 200
    d = res.json()
    assert any("$9B" in w for w in d["script"]["warnings"])
    assert d["script"]["hashtags"] == ["Chips"]  # cleaned and de-duplicated
    assert d["stages"]["script"]["edited"] is True
    # a backed number clears the warning again
    d = c.put(f"/api/jobs/{job.id}/script", json=_body(job, value="$499")).json()
    assert not any("$499" in w for w in d["script"]["warnings"])


def test_script_limits_are_enforced(env):
    _, job, _ = env
    c = TestClient(create_app(background=False))
    res = c.put(f"/api/jobs/{job.id}/script", json=_body(job, value="$1234567890"))
    assert res.status_code == 422
    assert "longer than" in res.json()["detail"]


def test_paths_stay_inside_the_job(env):
    _, job, _ = env
    c = TestClient(create_app(background=False))
    assert c.get(f"/api/jobs/{job.id}/files/../../config.yaml").status_code == 404
    assert c.get(f"/api/jobs/{job.id}/files/story.json").status_code == 200
    assert c.get("/api/jobs/..%2F..%2Fetc/files/x.json").status_code == 404
    assert c.get("/api/jobs/nope").status_code == 404


def test_publish_needs_a_video(env):
    _, job, _ = env
    c = TestClient(create_app(background=False))
    res = c.post(f"/api/jobs/{job.id}/publish", json={"dry_run": True})
    assert res.status_code == 409


def test_token_guards_the_api(env):
    c = TestClient(create_app("s3cret", background=False))
    assert c.get("/api/jobs").status_code == 401
    assert c.get("/api/session").json() == {"auth_required": True, "signed_in": False}
    assert c.post("/api/login", json={"token": "nope"}).status_code == 401
    assert c.post("/api/login", json={"token": "s3cret"}).status_code == 200
    assert c.get("/api/jobs").status_code == 200
    assert TestClient(create_app("s3cret", background=False)).get("/api/jobs", headers={"Authorization": "Bearer s3cret"}).status_code == 200


def test_auto_runs_once_a_day(tmp_path: Path):
    store = AutoStore(tmp_path / "auto.json")
    store.save(AutoSettings(enabled=True, time="08:00"), AutoState())
    calls: list[AutoSettings] = []
    sched = AutoScheduler(store, lambda s: (calls.append(s), ("t1", None))[1])
    assert not sched.tick(datetime(2026, 10, 20, 7, 59))
    assert sched.tick(datetime(2026, 10, 20, 9, 30))  # app started late: catches up that day
    assert not sched.tick(datetime(2026, 10, 20, 23, 0))  # never twice
    assert sched.tick(datetime(2026, 10, 21, 8, 0))
    assert len(calls) == 2
    settings, state = store.load()
    assert state.last_run_date == "2026-10-21" and state.last_task == "t1"
    assert not due(settings.model_copy(update={"enabled": False}), AutoState(), datetime(2026, 10, 22, 9))


def test_settings_keep_config_comments(env):
    _, _, cfg_file = env
    cfg = update_config({"voice.speed": 1.05, "render.style": "kinetic"})
    assert cfg.voice.speed == 1.05 and cfg.render.style == "kinetic"
    text = cfg_file.read_text(encoding="utf-8")
    assert "# keep this comment" in text and "# Test config" in text
    with pytest.raises(ValueError):
        update_config({"render.style": "nope"})
    with pytest.raises(ValueError):
        update_config({"paths.output_dir": "/tmp"})


def test_settings_voice_engine(env):
    c = TestClient(create_app(background=False))
    s = c.get("/api/settings").json()
    assert s["engine"] == "kokoro" and set(s["options"]["voices"]) == {"kokoro", "chatterbox", "elevenlabs"}
    assert s["options"]["voices"]["chatterbox"] == ["default"]
    kokoro_speed = s["speed"]
    s = c.put("/api/settings", json={"engine": "elevenlabs", "voice": "Sarah", "speed": 1.1}).json()
    assert (s["engine"], s["voice"], s["speed"]) == ("elevenlabs", "Sarah", 1.1)
    assert s["engines"]["kokoro"]["speed"] == kokoro_speed  # the other engines keep their own settings
    s = c.put("/api/settings", json={"engine": "chatterbox", "voice": "default", "speed": 1.3}).json()
    assert (s["engine"], s["speed"]) == ("chatterbox", None)  # Chatterbox has no speed control
    assert c.put("/api/settings", json={"engine": "elevenlabs", "speed": 1.9}).status_code == 422


def test_feeds_save_over_the_defaults(env):
    _, _, cfg_file = env
    c = TestClient(create_app(background=False))
    data = c.get("/api/feeds").json()
    assert len(data["feeds"]) == 7 and data["hacker_news"] is True  # nothing in config.yaml yet: the built-in list
    feeds = data["feeds"] + [{"name": "Example", "url": "https://example.org/feed", "weight": 1}]
    assert c.put("/api/feeds", json={"feeds": feeds, "hacker_news": False}).status_code == 200
    load_config.cache_clear()
    cfg = load_config()
    assert len(cfg.news.feeds) == 8 and not cfg.news.hacker_news.enabled
    assert next(f for f in cfg.news.feeds if f.name == "Wired").weight == 0.9
    text = cfg_file.read_text(encoding="utf-8")
    assert "# keep this comment" in text and '    - {name: Example, url: "https://example.org/feed"}' in text
    dupe = feeds + [{"name": "example", "url": "https://example.org/other", "weight": 1}]
    assert c.put("/api/feeds", json={"feeds": dupe}).status_code == 422
    assert c.put("/api/feeds", json={"feeds": [{"name": "Bad", "url": "ftp://x", "weight": 1}]}).status_code == 422


def test_feed_check_finds_the_feed_a_site_links(env, monkeypatch):
    import httpx

    from technews.news import sources

    rss = (Path(__file__).parent / "fixtures" / "feed_ars.xml").read_bytes()

    def handler(request: httpx.Request) -> httpx.Response:
        at = (request.url.host, request.url.path)
        if at in {("linked.example", "/news/feed.xml"), ("plain.example", "/rss.xml")}:
            return httpx.Response(200, content=rss)
        if at == ("linked.example", "/"):
            return httpx.Response(200, html='<head><link rel="alternate" type="application/rss+xml" href="/news/feed.xml"></head>')
        return httpx.Response(200, html="<p>No feed here</p>") if request.url.path == "/" else httpx.Response(404)

    monkeypatch.setattr(sources, "make_client", lambda cfg: httpx.Client(transport=httpx.MockTransport(handler)))
    c = TestClient(create_app(background=False))
    found = c.post("/api/feeds/check", json={"url": "linked.example"}).json()  # the page names its feed
    assert found["url"] == "https://linked.example/news/feed.xml" and found["entries"] > 0 and found["name"]
    found = c.post("/api/feeds/check", json={"url": "https://plain.example"}).json()  # a feed at a usual path
    assert found["url"] == "https://plain.example/rss.xml"
    assert c.post("/api/feeds/check", json={"url": "https://empty.example"}).status_code == 422


def test_pasted_article_is_the_only_source(env, monkeypatch):
    from technews import news, pipeline
    from technews.script import prompts

    seen = {}

    def fake_make(cfg, *, story, **_):
        seen["story"] = story
        return pipeline.start_job(cfg, story)

    monkeypatch.setattr(pipeline, "make", fake_make)
    monkeypatch.setattr(news, "enrich", lambda *a, **k: pytest.fail("the pasted text was swapped for a page fetch"))
    app = create_app(background=False)
    c = TestClient(app)
    text = "The company announced a laptop processor it says is 30% faster than the previous generation. " * 3
    assert c.post("/api/jobs", json={"article": {"title": "Chip", "text": "Too short."}}).status_code == 422
    body = {"article": {"title": "  New   laptop chip ", "text": text, "url": "https://example.org/a"}}
    assert c.post("/api/jobs", json=body).status_code == 200
    task, work = app.state.worker._queue.popleft()
    work(task, pipeline.Hooks())
    story = seen["story"]
    assert story.title == "New laptop chip" and story.source == "example.org" and story.text == text.strip()
    assert task.result["job"]

    system, user = prompts(story.model_copy(update={"source": "", "url": ""}), env[0])
    assert "according to" not in system and "SOURCE:" not in user and "URL:" not in user
