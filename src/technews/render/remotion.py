"""Run the Remotion renderer (video/render.mjs) and relay its progress."""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from ..config import AppConfig

log = logging.getLogger(__name__)

CREATE_FLAGS = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


class RenderError(RuntimeError):
    pass


def node_path() -> str | None:
    return shutil.which("node")


def check_setup(cfg: AppConfig) -> None:
    if not node_path():
        raise RenderError("Node.js isn't on PATH. Install Node 20+ from https://nodejs.org")
    if not (cfg.paths.video / "node_modules" / "@remotion" / "renderer").exists():
        raise RenderError(f"Video dependencies aren't installed. Run: cd \"{cfg.paths.video}\" && npm install")


def run_render(
    cfg: AppConfig,
    props_path: Path,
    public_dir: Path,
    out: Path,
    still: str | None = None,
    on_progress: Callable[[str, float], None] | None = None,
) -> Path:
    check_setup(cfg)
    args = [node_path() or "node", str(cfg.paths.video / "render.mjs"), "--props", str(props_path),
            "--public-dir", str(public_dir), "--out", str(out)]
    if still is not None:
        args += ["--still", str(still)]
    browser = cfg.render.browser_executable or os.environ.get("REMOTION_BROWSER_EXECUTABLE")
    if browser:
        args += ["--browser", browser]
    if cfg.render.concurrency:
        args += ["--concurrency", str(cfg.render.concurrency)]
    if cfg.render.gl:
        args += ["--gl", cfg.render.gl]
    args += ["--crf", str(cfg.render.crf)]

    log.info("Rendering %s", out.name)
    proc = subprocess.Popen(
        args, cwd=cfg.paths.video, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        encoding="utf-8", errors="replace", creationflags=CREATE_FLAGS,
    )
    tail: list[str] = []
    error = ""
    assert proc.stdout is not None
    for line in proc.stdout:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            tail = (tail + [line])[-30:]
            log.debug("render> %s", line)
            continue
        stage = msg.get("stage", "")
        if stage == "error":
            error = msg.get("message", "")
        elif on_progress and "progress" in msg:
            on_progress(stage, float(msg["progress"]))
    code = proc.wait()
    if code != 0:
        detail = error or "\n".join(tail[-12:])
        raise RenderError(f"Remotion render failed (exit {code}):\n{detail}")
    return out
