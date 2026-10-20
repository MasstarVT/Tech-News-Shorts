"""One background worker for the web app: pipeline work is CPU-heavy, so tasks run one at a time."""

from __future__ import annotations

import logging
import threading
import time
import traceback
import uuid
from collections import deque
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime

from ..pipeline import Hooks

log = logging.getLogger(__name__)

# Stage names (from pipeline hooks) that put the tally "on air"; everything else running is standby.
LIVE_STAGES = ("Rendering", "Publishing")


@dataclass
class Task:
    id: str
    kind: str  # make | run | publish | auto
    title: str
    job_id: str | None = None
    status: str = "queued"  # queued | running | done | failed
    stage: str = ""
    progress: float | None = None
    created: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    started: str | None = None
    finished: str | None = None
    error: str = ""
    result: dict = field(default_factory=dict)

    def view(self) -> dict:
        d = asdict(self)
        d["live"] = self.status == "running" and self.stage.startswith(LIVE_STAGES)
        return d


Work = Callable[[Task, Hooks], None]


class Worker:
    def __init__(self, history: int = 30):
        self._queue: deque[tuple[Task, Work]] = deque()
        self._recent: deque[Task] = deque(maxlen=history)
        self._current: Task | None = None
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._stop = False
        self._thread = threading.Thread(target=self._loop, name="technews-worker", daemon=True)

    def start(self) -> None:
        if not self._thread.is_alive():
            self._thread.start()

    def stop(self) -> None:
        self._stop = True
        self._wake.set()

    # ------------------------------------------------------------------ state

    def submit(self, kind: str, title: str, work: Work, job_id: str | None = None) -> Task:
        task = Task(id=uuid.uuid4().hex[:10], kind=kind, title=title, job_id=job_id)
        with self._lock:
            self._queue.append((task, work))
        self._wake.set()
        return task

    def busy(self, job_id: str) -> bool:
        with self._lock:
            if self._current and self._current.job_id == job_id:
                return True
            return any(t.job_id == job_id for t, _ in self._queue)

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "current": self._current.view() if self._current else None,
                "queue": [t.view() for t, _ in self._queue],
                "recent": [t.view() for t in reversed(self._recent)],
            }

    def get(self, task_id: str) -> Task | None:
        with self._lock:
            if self._current and self._current.id == task_id:
                return self._current
            for t, _ in self._queue:
                if t.id == task_id:
                    return t
            return next((t for t in self._recent if t.id == task_id), None)

    # ------------------------------------------------------------------ loop

    def _hooks(self, task: Task) -> Hooks:
        def stage(name: str) -> None:
            task.stage = name
            task.progress = None

        def voice(done: int, total: int) -> None:
            task.progress = done / max(1, total)

        def download(name: str, done: int, total: int) -> None:
            task.stage = f"Downloading {name}"
            task.progress = done / total if total else None

        def render(stage: str, frac: float) -> None:
            if stage == "render":
                task.progress = frac
            elif stage == "bundle":
                task.progress = None

        return Hooks(stage=stage, voice_progress=voice, download_progress=download, render_progress=render)

    def _loop(self) -> None:
        while not self._stop:
            with self._lock:
                item = self._queue.popleft() if self._queue else None
                if item:
                    self._current = item[0]
            if not item:
                self._wake.wait(1.0)
                self._wake.clear()
                continue
            task, work = item
            task.status = "running"
            task.started = datetime.now().isoformat(timespec="seconds")
            t0 = time.monotonic()
            try:
                work(task, self._hooks(task))
                task.status = "done"
            except Exception as e:  # the task records the failure; the worker keeps going
                task.status = "failed"
                task.error = str(e)[:2000] or type(e).__name__
                log.error("Task %s (%s) failed: %s\n%s", task.id, task.title, e, traceback.format_exc())
            task.finished = datetime.now().isoformat(timespec="seconds")
            task.result.setdefault("seconds", round(time.monotonic() - t0, 1))
            with self._lock:
                self._current = None
                self._recent.append(task)
