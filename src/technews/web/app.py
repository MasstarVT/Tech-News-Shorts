"""The web app's API (FastAPI). `technews web` serves it together with the built frontend in web/dist."""

from __future__ import annotations

import hmac
import json
import logging
import re
import threading
import time
from contextlib import asynccontextmanager, contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .. import pipeline
from ..config import PROJECT_ROOT, AppConfig, load_config
from ..jobs import Job
from ..models import Script, ScriptScene, Story, Visual
from ..news.sources import discover_feed, site_name, story_id
from ..render.remotion import COMPOSITIONS
from ..script.normalize import LIMITS, review_script
from ..script.schema import ICONS_JSON, icon_names
from .auto import AutoScheduler, AutoSettings, AutoStore, next_run
from .settings import config_path, update_config
from .worker import Task, Worker

log = logging.getLogger(__name__)

DIST = PROJECT_ROOT / "web" / "dist"
JOB_ID = re.compile(r"^[A-Za-z0-9][\w.-]{0,120}$")
FILE_TYPES = {".mp4": "video/mp4", ".wav": "audio/wav", ".png": "image/png", ".json": "application/json", ".txt": "text/plain"}
STAGE_ORDER = ("script", "voice", "render")
STORY_TTL_S = 20 * 60
FALLBACK_VOICES = ["af_heart", "af_bella", "am_michael", "am_fenrir", "am_puck", "bf_emma", "bm_george"]
COOKIE = "tn_token"
ARTICLE_MIN, ARTICLE_MAX = 200, 20000  # characters of pasted article text


# --------------------------------------------------------------------------- request bodies


class SceneIn(BaseModel):
    narration: str = Field(min_length=1)
    visual: Visual


class ScriptIn(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    topic: str = ""
    description: str = ""
    hashtags: list[str] = Field(default_factory=list)
    scenes: list[SceneIn] = Field(min_length=1, max_length=12)


class ArticleIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    text: str = Field(max_length=ARTICLE_MAX)
    source: str = Field(default="", max_length=60)
    url: str = ""


class MakeIn(BaseModel):
    story_id: str | None = None
    url: str | None = None
    article: ArticleIn | None = None


class FeedIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    url: str = Field(min_length=1)
    weight: float = Field(default=1.0, ge=0, le=3)


class FeedsIn(BaseModel):
    feeds: list[FeedIn] = Field(max_length=60)
    hacker_news: bool | None = None


class FeedCheckIn(BaseModel):
    url: str = Field(min_length=1)


class RunIn(BaseModel):
    stages: list[Literal["script", "voice", "render"]] = Field(min_length=1)
    style: Literal["blueprint", "kinetic", "slideshow"] | None = None
    voice: str | None = None
    speed: float | None = Field(default=None, ge=0.5, le=2.0)
    llm: str | None = None


class PublishIn(BaseModel):
    targets: list[Literal["export", "youtube", "tiktok"]] | None = None
    dry_run: bool = False
    force: bool = False  # publish even though the video is older than the script


class SettingsIn(BaseModel):
    style: Literal["blueprint", "kinetic", "slideshow"] | None = None
    captions: bool | None = None
    voice: str | None = None
    speed: float | None = Field(default=None, ge=0.5, le=2.0)
    llm_provider: str | None = None
    llm_model: str | None = None
    llm_effort: str | None = None
    brand: str | None = Field(default=None, min_length=1, max_length=40)


class LoginIn(BaseModel):
    token: str


# --------------------------------------------------------------------------- helpers


def current_config() -> AppConfig:
    """The config, re-read when config.yaml changed on disk (the server runs for days; hand edits must count)."""
    m = _mtime(config_path())
    if m != _config_seen[0]:
        load_config.cache_clear()
        _config_seen[0] = m
    return load_config()


_config_seen = [0.0]


def _mtime(p: Path) -> float:
    return p.stat().st_mtime if p.exists() else 0.0


def _ago(ts: float) -> str:
    return datetime.fromtimestamp(ts).isoformat(timespec="seconds") if ts else ""


def _with_style(cfg: AppConfig, style: str | None) -> AppConfig:
    if not style:
        return cfg
    return cfg.model_copy(update={"render": cfg.render.model_copy(update={"style": style})})


@contextmanager
def _job_log(job: Job):
    handler = job.attach_log()
    try:
        yield
    finally:
        logging.getLogger().removeHandler(handler)
        handler.close()


def _visual_problems(v: Visual) -> list[str]:
    L = LIMITS
    checks = {
        "headline": [(v.text, L["headline"], "headline text"), (v.tag, L["tag"], "tag")],
        "stat": [(v.value, L["stat_value"], "stat value"), (v.label, L["stat_label"], "stat label")],
        "icon": [(v.text, L["icon_text"], "icon text")],
        "versus": [(v.left, L["versus_side"], "left side"), (v.right, L["versus_side"], "right side"),
                   (v.label, L["versus_label"], "versus label")],
        "bullets": [(i, L["bullet"], "bullet") for i in v.items],
        "outro": [],
    }[v.type]
    problems = [f"{name} is longer than {limit} characters" for text, limit, name in checks if len(text or "") > limit]
    if v.type == "stat" and not re.search(r"\d", v.value):
        problems.append("stat value needs a number")
    if v.type == "icon" and v.icon not in icon_names():
        problems.append(f"unknown icon '{v.icon}'")
    if v.type == "versus" and not (v.left.strip() and v.right.strip()):
        problems.append("versus needs both sides")
    if v.type == "bullets" and not 2 <= len([i for i in v.items if i.strip()]) <= L["bullets"]:
        problems.append(f"bullets need 2 to {L['bullets']} items")
    if v.type in ("headline", "icon") and not v.text.strip():
        problems.append(f"{v.type} needs text")
    return problems


def _article_story(a: ArticleIn) -> Story:
    """A story from text pasted into the web app; that text is the script writer's only source of facts."""
    title, text, url = " ".join(a.title.split()), a.text.strip(), a.url.strip()
    if not title:
        raise HTTPException(422, "Give the article a headline")
    if len(text) < ARTICLE_MIN:
        raise HTTPException(422, f"Paste more of the article: the script needs at least {ARTICLE_MIN} characters to work from")
    if url and not re.match(r"^https?://", url):
        raise HTTPException(422, "The source link must be a full http(s) link")
    source = " ".join(a.source.split()) or (site_name(url) if url else "")
    return Story(id=story_id(f"{title}\n{text}"), title=title, url=url, source=source, published=datetime.now(UTC),
                 summary=" ".join(text.split())[:600], text=text)


class StoryCache:
    def __init__(self):
        self.stories: list[Story] = []
        self.fetched = 0.0
        self.lock = threading.Lock()

    def get(self, cfg: AppConfig, refresh: bool) -> tuple[list[Story], float]:
        from .. import news

        with self.lock:
            if refresh or not self.fetched or time.time() - self.fetched > STORY_TTL_S:
                self.stories = news.candidates(cfg)
                self.fetched = time.time()
            return list(self.stories), self.fetched

    def invalidate(self) -> None:
        with self.lock:
            self.fetched = 0.0

    def take(self, story_id: str) -> Story | None:
        with self.lock:
            for i, s in enumerate(self.stories):
                if s.id == story_id:
                    return self.stories.pop(i)  # it becomes a job; history marks it covered
        return None


# --------------------------------------------------------------------------- app


def create_app(token: str | None = None, *, background: bool = True) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if background:
            app.state.worker.start()
            app.state.scheduler.start()
        yield
        app.state.worker.stop()
        app.state.scheduler.stop()

    app = FastAPI(title="Tech News Shorts", docs_url="/api/docs", openapi_url="/api/openapi.json", lifespan=lifespan)
    worker = Worker()
    stories = StoryCache()
    voices_cache: dict[str, list[str]] = {}
    auto_store = AutoStore(current_config().paths.data / "web" / "auto.json")
    app.state.worker = worker
    app.state.auto_store = auto_store

    # ------------------------------------------------------------------ auth

    @app.middleware("http")
    async def _auth(request: Request, call_next):
        path = request.url.path
        if token and path.startswith("/api/") and path not in ("/api/login", "/api/session"):
            supplied = request.cookies.get(COOKIE) or request.headers.get("authorization", "").removeprefix("Bearer ").strip()
            if not supplied or not hmac.compare_digest(supplied, token):
                return JSONResponse({"detail": "Sign in required"}, status_code=401)
        return await call_next(request)

    @app.get("/api/session")
    def session(request: Request):
        supplied = request.cookies.get(COOKIE) or ""
        return {"auth_required": bool(token), "signed_in": not token or hmac.compare_digest(supplied, token)}

    @app.post("/api/login")
    def login(body: LoginIn, request: Request):
        if not token or not hmac.compare_digest(body.token, token):
            raise HTTPException(401, "Wrong access token")
        res = JSONResponse({"ok": True})
        res.set_cookie(COOKIE, token, httponly=True, samesite="strict", secure=request.url.scheme == "https",
                       max_age=60 * 60 * 24 * 30)
        return res

    # ------------------------------------------------------------------ jobs

    def open_job(job_id: str) -> Job:
        cfg = current_config()
        root = cfg.paths.output.resolve()
        folder = (root / job_id).resolve()
        if not JOB_ID.match(job_id) or folder.parent != root or not (folder / "job.json").exists():
            raise HTTPException(404, f"No job '{job_id}'")
        return Job(folder, cfg)

    def staleness(job: Job, state, script: Script | None) -> dict:
        voice_stale = render_stale = False
        timing = job.voice_dir / "timing.json"
        if script and timing.exists():
            key = (state.stages.get("voice") or {}).get("narration")
            voice_stale = key != pipeline.narration_key(script) if key else _mtime(job.dir / "script.json") > _mtime(timing)
        if job.video_path.exists():
            render_stale = max(_mtime(job.dir / "script.json"), _mtime(timing)) > _mtime(job.video_path)
        return {"voice": voice_stale, "render": render_stale or voice_stale}

    def file_url(job: Job, p: Path) -> str:
        rel = p.relative_to(job.dir).as_posix()
        return f"/api/jobs/{job.id}/files/{rel}?v={int(_mtime(p))}"

    def summary(job: Job) -> dict:
        state = job.load_state()
        story = job.load_story()
        script = job.load_script() if job.has_script() else None
        stages = state.stages
        held = bool((stages.get("review") or {}).get("held"))
        frames, fps = None, cfg_fps()
        if job.has_voice():
            try:
                track = job.load_voice()
                frames, fps = sum(s.frames for s in track.scenes), track.fps
            except ValueError:
                pass
        return {
            "id": job.id,
            "title": script.title if script else story.title,
            "story_title": story.title,
            "source": story.source,
            "url": story.url,
            "created": state.created.isoformat(timespec="seconds"),
            "status": state.status,
            "error": (stages.get("error") or {}).get("error", "") if state.status == "failed" else "",
            "stages": {k: v for k, v in stages.items() if k in ("script", "voice", "render", "review")},
            "published": state.published,
            "warnings": len(script.warnings) if script else 0,
            "scenes": len(script.scenes) if script else 0,
            "seconds": (stages.get("voice") or {}).get("seconds"),
            "frames": frames,  # exact length; the UI derives every timecode from frames so totals agree
            "fps": fps,
            "style": (stages.get("render") or {}).get("style"),
            "video": file_url(job, job.video_path) if job.video_path.exists() else None,
            "held": held,
            "busy": worker.busy(job.id),
            "stale": staleness(job, state, script),
        }

    def cfg_fps() -> int:
        return current_config().render.fps

    def all_jobs() -> list[Job]:
        cfg = current_config()
        files = sorted(cfg.paths.output.glob("*/job.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        return [Job(f.parent, cfg) for f in files]

    @app.get("/api/jobs")
    def list_jobs(limit: int = 60):
        out = []
        for job in all_jobs()[:limit]:
            try:
                out.append(summary(job))
            except Exception as e:  # a half-written job folder shouldn't break the list
                out.append({"id": job.id, "title": job.id, "status": "unreadable", "error": str(e)[:200]})
        return out

    @app.get("/api/jobs/{job_id}")
    def job_detail(job_id: str):
        job = open_job(job_id)
        data = summary(job)
        story = job.load_story()
        data["story"] = story.model_dump(mode="json")
        data["script"] = job.load_script().model_dump(mode="json") if job.has_script() else None
        if job.has_voice():
            track = job.load_voice()
            data["voice"] = {"voice": track.voice, "speed": track.speed, "timed": track.timed,
                             "scenes": [{"id": s.id, "seconds": round(s.duration_s, 2), "frames": s.frames} for s in track.scenes]}
        else:
            data["voice"] = None
        meta = job.dir / "metadata.json"
        data["metadata"] = job.load_json("metadata.json") if meta.exists() else None
        data["videos"] = [
            {"name": p.name, "url": file_url(job, p), "mb": round(p.stat().st_size / 1e6, 1), "at": _ago(_mtime(p))}
            for p in sorted(job.dir.glob("*.mp4"))
        ]
        data["log"] = job.log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-80:] if job.log_path.exists() else []
        return data

    @app.get("/api/jobs/{job_id}/files/{rel:path}")
    def job_file(job_id: str, rel: str):
        job = open_job(job_id)
        root = job.dir.resolve()
        p = (root / rel).resolve()
        if not p.is_relative_to(root) or not p.is_file() or p.suffix.lower() not in FILE_TYPES:
            raise HTTPException(404, "No such file")
        return FileResponse(p, media_type=FILE_TYPES[p.suffix.lower()], headers={"Cache-Control": "no-cache"})

    def ensure_idle(job: Job) -> None:
        if worker.busy(job.id):
            raise HTTPException(409, "This job is busy; wait for its current task to finish")

    @app.put("/api/jobs/{job_id}/script")
    def save_script(job_id: str, body: ScriptIn):
        job = open_job(job_id)
        ensure_idle(job)
        if not job.has_script():
            raise HTTPException(409, "This job has no script yet")
        problems = [f"Scene {i + 1}: {p}" for i, s in enumerate(body.scenes) for p in _visual_problems(s.visual)]
        if problems:
            raise HTTPException(422, "; ".join(problems))
        cfg = current_config()
        old = job.load_script()
        tags = []
        for h in body.hashtags:
            tag = re.sub(r"[^A-Za-z0-9_]", "", h.lstrip("#"))
            if tag and tag.lower() not in {t.lower() for t in tags}:
                tags.append(tag)
        scenes = [ScriptScene(id=f"s{i:02d}", narration=" ".join(s.narration.split()), visual=s.visual) for i, s in enumerate(body.scenes)]
        new = Script(title=body.title.strip(), topic=body.topic.strip() or old.topic, description=body.description.strip(),
                     hashtags=tags[:6], scenes=scenes, llm=old.llm, warnings=[])
        new.warnings = review_script(new, job.load_story(), cfg)
        same = new.model_dump(exclude={"warnings"}) == old.model_dump(exclude={"warnings"})
        if not same or new.warnings != old.warnings:
            job.save_script(new)
            job.mark("script", None, llm=old.llm, words=new.word_count, warnings=len(new.warnings), edited=True)
        return job_detail(job_id)

    def queue_run(job: Job, stages: list[str], style: str | None = None, voice: str | None = None,
                  speed: float | None = None, llm: str | None = None) -> Task:
        ordered = [s for s in STAGE_ORDER if s in stages]

        def work(task: Task, hooks: pipeline.Hooks) -> None:
            cfg = _with_style(current_config(), style)
            with _job_log(job):
                try:
                    if "script" in ordered:
                        hooks.stage("Writing the script")
                        pipeline.stage_script(job, cfg, llm)
                    if "voice" in ordered:
                        hooks.stage("Recording the voice")
                        pipeline.stage_voice(job, cfg, voice, speed, hooks=hooks)
                    if "render" in ordered:
                        hooks.stage(f"Rendering ({cfg.render.style})")
                        pipeline.stage_render(job, cfg, hooks)
                except Exception as e:
                    job.mark("error", "failed", error=str(e)[:500])
                    raise

        label = " + ".join(ordered)
        return worker.submit("run", f"{label.capitalize()}: {job.load_story().title}", work, job_id=job.id)

    @app.post("/api/jobs/{job_id}/run")
    def run_stages(job_id: str, body: RunIn):
        job = open_job(job_id)
        ensure_idle(job)
        if "script" not in body.stages and not job.has_script():
            raise HTTPException(409, "Write the script first")
        if "render" in body.stages and "voice" not in body.stages and not job.has_voice():
            raise HTTPException(409, "Record the voice first")
        return queue_run(job, body.stages, body.style, body.voice, body.speed, body.llm).view()

    @app.post("/api/jobs/{job_id}/publish")
    def publish(job_id: str, body: PublishIn):
        job = open_job(job_id)
        ensure_idle(job)
        if not job.video_path.exists():
            raise HTTPException(409, "Render the video first")
        state = job.load_state()
        script = job.load_script() if job.has_script() else None
        if staleness(job, state, script)["render"] and not body.force:
            raise HTTPException(409, "The video is older than the script. Re-render it, or publish anyway.")

        def work(task: Task, hooks: pipeline.Hooks) -> None:
            from ..publish import notify, publish_job

            cfg = current_config()
            with _job_log(job):
                hooks.stage("Publishing" + (" (dry run)" if body.dry_run else ""))
                results = publish_job(job, cfg, only=body.targets, dry_run=body.dry_run)
                if not body.dry_run:
                    notify(job, cfg, results)
                    job.mark("review", None, held=False, approved=datetime.now().isoformat(timespec="seconds"))
            task.result["published"] = results

        return worker.submit("publish", f"Publish: {job.load_story().title}", work, job_id=job.id).view()

    @app.post("/api/jobs/{job_id}/reject")
    def reject(job_id: str):
        job = open_job(job_id)
        ensure_idle(job)
        job.mark("review", None, held=False, rejected=datetime.now().isoformat(timespec="seconds"))
        return summary(job)

    def queue_make(story: Story | None, url: str | None, title: str, publish: bool = False,
                   only: list[str] | None = None, dry_run: bool = False, hold: bool = False, kind: str = "make",
                   fetch: bool = True) -> Task:
        def work(task: Task, hooks: pipeline.Hooks) -> None:
            def on_job(job: Job) -> None:
                task.job_id = job.id

            cfg = current_config()
            if not fetch:  # pasted text is the whole source; don't swap it for whatever its link's page says
                cfg = cfg.model_copy(update={"news": cfg.news.model_copy(update={"fetch_article": False})})
            job = pipeline.make(cfg, url=url, story=story, render=True, publish=publish, only=only,
                                dry_run=dry_run, hooks=hooks, on_job=on_job)
            if hold:
                job.mark("review", None, held=True)
            task.result["job"] = job.id

        return worker.submit(kind, title, work)

    @app.post("/api/jobs")
    def make(body: MakeIn):
        if body.article:
            story = _article_story(body.article)
            return queue_make(story, None, f"Make: {story.title}", fetch=False).view()
        if body.story_id:
            story = stories.take(body.story_id)
            if not story:
                raise HTTPException(404, "That story is no longer in the list; refresh the wire")
            return queue_make(story, None, f"Make: {story.title}").view()
        if body.url:
            if not re.match(r"^https?://", body.url):
                raise HTTPException(422, "Paste a full http(s) link")
            return queue_make(None, body.url, f"Make: {body.url}").view()
        return queue_make(None, None, "Make: today's top story").view()

    # ------------------------------------------------------------------ stories, tasks, meta

    @app.get("/api/stories")
    def list_stories(refresh: bool = False):
        cfg = current_config()
        items, fetched = stories.get(cfg, refresh)
        return {
            "fetched": _ago(fetched),
            "stories": [
                {"id": s.id, "title": s.title, "url": s.url, "source": s.source,
                 "published": s.published.isoformat() if s.published else None, "summary": s.summary[:400],
                 "points": s.points, "comments": s.comments, "discussion_url": s.discussion_url,
                 "also_in": s.also_in, "score": round(s.score, 2)}
                for s in items
            ],
        }

    def feeds_view(cfg: AppConfig) -> dict:
        return {"feeds": [f.model_dump() for f in cfg.news.feeds], "hacker_news": cfg.news.hacker_news.enabled}

    @app.get("/api/feeds")
    def get_feeds():
        return feeds_view(current_config())

    @app.put("/api/feeds")
    def put_feeds(body: FeedsIn):
        feeds: list[dict] = []
        names: set[str] = set()
        urls: set[str] = set()
        for f in body.feeds:
            name, url = " ".join(f.name.split()), f.url.strip()
            if not name:
                raise HTTPException(422, "Every feed needs a name")
            if not re.match(r"^https?://", url):
                raise HTTPException(422, f"{name}: the feed address must be a full http(s) link")
            # The name becomes each story's source, and weights and outlet clustering go by it.
            if name.lower() in names or url.lower() in urls:
                raise HTTPException(422, f"{name} is in the list twice")
            names.add(name.lower())
            urls.add(url.lower())
            feeds.append({"name": name, "url": url} | ({"weight": f.weight} if f.weight != 1.0 else {}))
        changes: dict = {"news.feeds": feeds}
        if body.hacker_news is not None:
            changes["news.hacker_news.enabled"] = body.hacker_news
        try:
            cfg = update_config(changes)
        except ValueError as e:
            raise HTTPException(422, str(e)) from e
        stories.invalidate()
        return feeds_view(cfg)

    @app.post("/api/feeds/check")
    def check_feed(body: FeedCheckIn):
        url = body.url.strip()
        if not re.match(r"^https?://", url):
            url = f"https://{url}"
        try:
            feed_url, name, entries = discover_feed(url, current_config())
        except httpx.HTTPError as e:
            raise HTTPException(422, f"Couldn't open that address: {str(e)[:200]}") from e
        except ValueError as e:
            raise HTTPException(422, str(e)) from e
        return {"url": feed_url, "name": name, "entries": entries}

    @app.get("/api/tasks")
    def tasks():
        return worker.snapshot()

    @app.get("/api/tasks/{task_id}")
    def task(task_id: str):
        t = worker.get(task_id)
        if not t:
            raise HTTPException(404, "No such task")
        return t.view()

    @app.get("/api/meta")
    def meta():
        cfg = current_config()
        return {
            "brand": cfg.brand.name,
            "styles": list(COMPOSITIONS),
            "limits": LIMITS,
            "icons": json.loads(ICONS_JSON.read_text(encoding="utf-8")),  # friendly name -> lucide icon
            "visual_types": ["headline", "stat", "icon", "versus", "bullets", "outro"],
            "targets": [t.model_dump() for t in cfg.publish.targets],
            "defaults": {"style": cfg.render.style, "voice": cfg.voice.voice, "speed": cfg.voice.speed},
        }

    # ------------------------------------------------------------------ settings + health

    def ollama_models(cfg: AppConfig) -> list[str]:
        base = cfg.llm.providers.get("ollama")
        if not base or not base.base_url:
            return []
        try:
            r = httpx.get(f"{base.base_url.rstrip('/')}/api/tags", timeout=2)
            return sorted(m["name"] for m in r.json().get("models", []))
        except (httpx.HTTPError, ValueError, KeyError):
            return []

    def voices(cfg: AppConfig) -> list[str]:
        if "list" in voices_cache:
            return voices_cache["list"]
        from ..voice.kokoro import KokoroEngine, model_paths

        if not all(p.exists() for p in model_paths(cfg)):
            return FALLBACK_VOICES
        try:

            voices_cache["list"] = sorted(KokoroEngine(cfg).voices())
        except Exception:
            return FALLBACK_VOICES
        return voices_cache["list"]

    @app.get("/api/settings")
    def get_settings():
        cfg = current_config()
        route = cfg.llm.tasks.get("script")
        return {
            "style": cfg.render.style,
            "captions": cfg.render.captions.enabled,
            "voice": cfg.voice.voice,
            "speed": cfg.voice.speed,
            "llm": {"provider": route.provider if route else "null", "model": route.model if route else "",
                    "effort": route.effort if route else None},
            "brand": cfg.brand.name,
            "options": {"styles": list(COMPOSITIONS), "voices": voices(cfg), "ollama_models": ollama_models(cfg),
                        "providers": list(cfg.llm.providers)},
        }

    @app.put("/api/settings")
    def put_settings(body: SettingsIn):
        mapping = {"style": "render.style", "captions": "render.captions.enabled", "voice": "voice.voice",
                   "speed": "voice.speed", "llm_provider": "llm.tasks.script.provider",
                   "llm_model": "llm.tasks.script.model", "llm_effort": "llm.tasks.script.effort", "brand": "brand.name"}
        changes = {mapping[k]: v for k, v in body.model_dump(exclude_unset=True).items()}
        if "llm.tasks.script.effort" in changes and changes["llm.tasks.script.effort"] == "":
            changes["llm.tasks.script.effort"] = None
        try:
            update_config(changes)
        except ValueError as e:
            raise HTTPException(422, str(e)) from e
        return get_settings()

    @app.get("/api/health")
    def health():
        from ..doctor import run_checks

        load_config.cache_clear()
        out = []
        for c in run_checks(current_config()):
            status = c.status
            # Turned off or optional-and-unset is neither healthy nor broken: the UI shows it as an unlit light.
            if status == "ok" and c.detail.startswith(("disabled", "not set")):
                status = "off"
            out.append({"name": c.name, "status": status, "detail": c.detail, "fix": c.fix})
        return out

    # ------------------------------------------------------------------ auto mode

    def submit_auto(settings: AutoSettings) -> tuple[str, str | None]:
        publish = settings.mode == "publish"
        t = queue_make(None, None, "Auto: today's top story", publish=publish, only=settings.targets or None,
                       dry_run=settings.dry_run, hold=not publish, kind="auto")
        return t.id, t.job_id

    scheduler = AutoScheduler(auto_store, submit_auto)
    app.state.scheduler = scheduler

    def auto_view() -> dict:
        settings, state = auto_store.load()
        nr = next_run(settings, state)
        return {"settings": settings.model_dump(), "state": state.model_dump(),
                "next_run": nr.isoformat(timespec="minutes") if nr else None}

    @app.get("/api/auto")
    def get_auto():
        return auto_view()

    @app.put("/api/auto")
    def put_auto(body: AutoSettings):
        _, state = auto_store.load()
        auto_store.save(body, state)
        return auto_view()

    @app.post("/api/auto/run-now")
    def auto_run_now():
        settings, state = auto_store.load()
        task_id, _ = submit_auto(settings)
        state.last_task = task_id
        auto_store.save(settings, state)
        return auto_view()

    # ------------------------------------------------------------------ frontend

    if (DIST / "assets").exists():
        app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{rest:path}", include_in_schema=False)
    def spa(rest: str):
        if rest.startswith("api/"):
            raise HTTPException(404, "Not found")
        candidate = (DIST / rest).resolve()
        if rest and candidate.is_file() and candidate.is_relative_to(DIST.resolve()):
            return FileResponse(candidate)
        index = DIST / "index.html"
        if not index.exists():
            return JSONResponse({"detail": "The web app isn't built yet: cd web && npm install && npm run build"}, status_code=503)
        return FileResponse(index, headers={"Cache-Control": "no-cache"})

    return app


def serve(host: str = "127.0.0.1", port: int = 8765, open_browser: bool = True) -> None:
    import webbrowser

    import uvicorn

    from ..config import secret

    token = secret("TECHNEWS_WEB_TOKEN")
    if host not in ("127.0.0.1", "localhost", "::1") and not token:
        raise SystemExit("Refusing to listen on a network address without TECHNEWS_WEB_TOKEN set in .env")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s", datefmt="%H:%M:%S")
    if not (DIST / "index.html").exists():
        log.warning("web/dist is missing - build the frontend: cd web && npm install && npm run build")
    app = create_app(token)
    url = f"http://{'127.0.0.1' if host in ('0.0.0.0', '::') else host}:{port}/"
    if open_browser:
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host=host, port=port, log_level="info")
