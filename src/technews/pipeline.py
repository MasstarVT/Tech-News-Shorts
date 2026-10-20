"""The whole run: pick a story -> script -> voice -> render -> (notify, publish)."""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable
from dataclasses import dataclass, field

from . import news
from .config import AppConfig
from .jobs import Job
from .models import Script, Story
from .news import history

log = logging.getLogger(__name__)


class NoStories(RuntimeError):
    pass


@dataclass
class Hooks:
    """Optional callbacks so the CLI can draw progress bars."""

    stage: Callable[[str], None] = lambda name: None
    voice_progress: Callable[[int, int], None] | None = None
    download_progress: Callable[[str, int, int], None] | None = None
    render_progress: Callable[[str, float], None] | None = None
    extra: dict = field(default_factory=dict)


def choose_story(cfg: AppConfig, pick: int | None = None, url: str | None = None) -> Story:
    if url:
        return news.story_from_url(url, cfg)
    ranked = news.candidates(cfg)
    if not ranked:
        raise NoStories("No fresh stories found (feeds unreachable, or everything was covered already)")
    index = (pick or 1) - 1
    if not 0 <= index < len(ranked):
        raise NoStories(f"There are only {len(ranked)} candidates; pick 1-{len(ranked)}")
    return ranked[index]


def narration_key(script: Script) -> str:
    """Fingerprint of what the voice reads; a changed key means the voice is out of date."""
    text = "\n".join(f"{s.id}:{s.narration}" for s in script.scenes)
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def start_job(cfg: AppConfig, story: Story) -> Job:
    if cfg.news.fetch_article:
        story = news.enrich(story, cfg)
    job = Job.create(cfg, story)
    history.add(cfg, story, job.id)
    return job


def stage_script(job: Job, cfg: AppConfig, llm: str | None = None) -> None:
    from .script import write_script

    script = write_script(job.load_story(), cfg, override=llm)
    job.save_script(script)
    job.mark("script", "scripted", llm=script.llm, words=script.word_count, warnings=len(script.warnings))


def stage_voice(job: Job, cfg: AppConfig, voice: str | None = None, speed: float | None = None, hooks: Hooks | None = None) -> None:
    from .voice import synthesize_job

    hooks = hooks or Hooks()
    track = synthesize_job(job, cfg, voice=voice, speed=speed, progress=hooks.voice_progress,
                           download_progress=hooks.download_progress)
    job.mark("voice", "voiced", engine=track.engine, voice=track.voice, seconds=round(track.duration_s, 1),
             timed=track.timed, warnings=len(track.warnings), narration=narration_key(job.load_script()))


def stage_render(job: Job, cfg: AppConfig, hooks: Hooks | None = None) -> None:
    from .render import render_job

    hooks = hooks or Hooks()
    path = render_job(job, cfg, on_progress=hooks.render_progress)
    job.mark("render", "rendered", video=path.name, mb=round(path.stat().st_size / 1e6, 1), style=cfg.render.style)


def make(
    cfg: AppConfig,
    *,
    pick: int | None = None,
    url: str | None = None,
    llm: str | None = None,
    voice: str | None = None,
    render: bool = True,
    publish: bool = False,
    only: list[str] | None = None,
    dry_run: bool = False,
    hooks: Hooks | None = None,
    story: Story | None = None,
    on_job: Callable[[Job], None] | None = None,
) -> Job:
    """``story`` skips the pick (the web app passes the row that was clicked); ``on_job`` sees the job folder
    as soon as it exists."""
    hooks = hooks or Hooks()
    if story is None:
        hooks.stage("Finding today's stories")
        story = choose_story(cfg, pick, url)
    hooks.stage(f"Reading: {story.title}")
    job = start_job(cfg, story)
    if on_job:
        on_job(job)
    handler = job.attach_log()
    try:
        log.info("Job %s: %s (%s)", job.id, story.title, story.url)
        hooks.stage("Writing the script")
        stage_script(job, cfg, llm)
        hooks.stage("Recording the voice")
        stage_voice(job, cfg, voice, hooks=hooks)
        if render:
            hooks.stage("Rendering the video")
            stage_render(job, cfg, hooks)
            from .publish import notify, publish_job

            notify(job, cfg)
            if publish:
                hooks.stage("Publishing")
                results = publish_job(job, cfg, only=only, dry_run=dry_run)
                notify(job, cfg, results)
        return job
    except Exception as e:
        job.mark("error", "failed", error=str(e)[:500])
        raise
    finally:
        logging.getLogger().removeHandler(handler)
        handler.close()
