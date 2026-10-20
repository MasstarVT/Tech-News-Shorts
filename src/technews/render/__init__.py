"""Render stage: script + voice -> props.json -> video.mp4 (Remotion)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from ..config import AppConfig
from ..jobs import Job
from .props import build_props
from .remotion import RenderError, check_setup, run_render

__all__ = ["RenderError", "build_props", "check_setup", "render_job", "render_still"]


def render_job(job: Job, cfg: AppConfig, on_progress: Callable[[str, float], None] | None = None) -> Path:
    build_props(job, cfg)
    return run_render(cfg, job.props_path, job.dir, job.video_path, on_progress=on_progress)


def render_still(job: Job, cfg: AppConfig, frames: str, out: Path | None = None) -> Path:
    """Render single frames (``frames`` is "45" or "10,80,200") to PNGs for a quick look."""
    build_props(job, cfg)
    many = "," in frames
    target = out or (job.dir / ("stills" if many else f"frame-{int(frames):04d}.png"))
    return run_render(cfg, job.props_path, job.dir, target, still=frames)
