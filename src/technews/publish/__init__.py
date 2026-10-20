"""Publish stage: export folder, YouTube Shorts, TikTok (inbox draft), with results saved in job.json."""

from __future__ import annotations

import logging
from datetime import datetime

from ..config import AppConfig, PublishTarget
from ..jobs import Job
from .base import PostRequest, Publisher, PublishError, RetryLater
from .discord import notify
from .export import export_job

log = logging.getLogger(__name__)

__all__ = ["PublishError", "RetryLater", "build_metadata", "get_publisher", "notify", "publish_job"]


def get_publisher(platform: str, account_id: str) -> Publisher:
    if platform == "youtube":
        from .youtube import YouTubePublisher

        return YouTubePublisher(account_id)
    if platform == "tiktok":
        from .tiktok import TikTokPublisher

        return TikTokPublisher(account_id)
    raise PublishError(f"No publisher for {platform}")


def build_metadata(job: Job, cfg: AppConfig) -> dict:
    script = job.load_script()
    story = job.load_story()
    origin = " - ".join(x for x in (story.source, story.url) if x)
    credit = f"Source: {origin}" if origin else ""
    if story.also_in:
        credit += f"\nAlso reported by {', '.join(story.also_in)}."
    tags = " ".join(f"#{h}" for h in script.hashtags)
    meta = {
        "youtube": {
            "title": script.title[:100],
            "description": "\n\n".join(x for x in (script.description, credit.strip(), "Script written with AI from the "
                                     "source article; narration is an AI voice.") if x),
            "hashtags": script.hashtags,
        },
        "tiktok": {"caption": f"{script.title} {tags}".strip()[:2200], "hashtags": script.hashtags},
    }
    job.save_json("metadata.json", meta)
    return meta


def _targets(cfg: AppConfig, only: list[str] | None) -> list[PublishTarget]:
    if not only:
        return [t for t in cfg.publish.targets if t.enabled]
    by_platform = {t.platform: t for t in cfg.publish.targets}
    return [by_platform.get(p) or PublishTarget(platform=p) for p in only]  # type: ignore[arg-type]


def publish_job(job: Job, cfg: AppConfig, only: list[str] | None = None, dry_run: bool = False) -> dict[str, dict]:
    if not job.video_path.exists():
        raise PublishError(f"No video yet - run `technews render {job.id}`")
    meta = build_metadata(job, cfg)
    results: dict[str, dict] = {}
    for target in _targets(cfg, only):
        at = datetime.now().isoformat(timespec="seconds")
        if dry_run:
            results[target.platform] = {"status": "dry_run", "at": at}
            continue
        try:
            if target.platform == "export":
                path = export_job(job, cfg, meta)
                results["export"] = {"status": "published", "path": str(path), "at": at}
                continue
            m = meta[target.platform]
            req = PostRequest(
                video=job.video_path,
                title=m["title"] if target.platform == "youtube" else m["caption"],
                description=m.get("description", ""),
                hashtags=m["hashtags"],
                privacy=target.privacy,
                mode=target.mode,
                ai_generated=cfg.publish.tiktok_ai_label,
            )
            res = get_publisher(target.platform, target.account).publish(req)
            results[target.platform] = {"status": res.status, "url": res.url, "remote_id": res.remote_id, "at": at,
                                        **({"state": res.state} if res.state else {})}
        except (PublishError, RetryLater) as e:
            log.error("%s: %s", target.platform, e)
            results[target.platform] = {"status": "failed", "error": str(e)[:500], "at": at}
    state = job.load_state()
    state.published.update(results)
    if any(r["status"] in ("published", "needs_action") for r in results.values()):
        state.status = "published"
    job.save_state(state)
    return results
