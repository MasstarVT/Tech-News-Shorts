"""Export target: copy the video and ready-to-paste captions into a folder (e.g. one that syncs to your phone)."""

from __future__ import annotations

import shutil
from pathlib import Path

from ..config import AppConfig
from ..jobs import Job


def export_job(job: Job, cfg: AppConfig, meta: dict) -> Path:
    folder = cfg.paths.resolve(cfg.publish.export_dir)
    folder.mkdir(parents=True, exist_ok=True)
    video = folder / f"{job.id}.mp4"
    shutil.copyfile(job.video_path, video)
    text = (
        f"YOUTUBE TITLE\n{meta['youtube']['title']}\n\n"
        f"YOUTUBE DESCRIPTION\n{meta['youtube']['description']}\n\n"
        f"TIKTOK CAPTION\n{meta['tiktok']['caption']}\n"
    )
    (folder / f"{job.id}.txt").write_text(text, encoding="utf-8")
    return video
