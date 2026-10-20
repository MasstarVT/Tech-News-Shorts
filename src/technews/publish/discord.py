"""Post finished videos to a Discord channel through a webhook, so you can review them from your phone."""

from __future__ import annotations

import json
import logging

import httpx

from ..config import AppConfig, secret
from ..jobs import Job

log = logging.getLogger(__name__)

MAX_UPLOAD = 10 * 1024 * 1024  # webhook attachment limit on servers without boosts


def notify(job: Job, cfg: AppConfig, results: dict | None = None) -> bool:
    url = secret(cfg.publish.discord_webhook_env)
    if not url:
        return False
    script = job.load_script()
    story = job.load_story()
    origin = " ".join(x for x in (story.source, f"<{story.url}>" if story.url else "") if x)
    lines = [f"**{script.title}**"] + ([f"Source: {origin}"] if origin else [])
    warnings = script.warnings + (job.load_voice().warnings if job.has_voice() else [])
    if warnings:
        lines.append("Check before posting:")
        lines += [f"- {w}" for w in warnings[:6]]
    for platform, res in (results or {}).items():
        status = res.get("status", "")
        link = res.get("url") or res.get("path") or res.get("error", "")
        lines.append(f"{platform}: {status} {link}".strip())
    lines.append(f"Job: `{job.id}`")
    content = "\n".join(lines)[:1900]

    try:
        video = job.video_path
        if not results and video.exists() and video.stat().st_size <= MAX_UPLOAD:
            with video.open("rb") as fh:
                r = httpx.post(url, data={"payload_json": json.dumps({"content": content})},
                               files={"files[0]": (f"{job.id}.mp4", fh, "video/mp4")}, timeout=120)
        else:
            if not results and video.exists():
                content += "\n(video is over Discord's 10 MB webhook limit; it's in the job folder)"
            r = httpx.post(url, json={"content": content}, timeout=30)
        r.raise_for_status()
        return True
    except httpx.HTTPError as e:
        log.warning("Discord notification failed: %s", e)
        return False
