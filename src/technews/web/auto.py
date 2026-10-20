"""Auto mode: make (and optionally publish) one video a day while the web app is running.

Runs once per day at or after the set time. A run missed because the app was closed happens when the app
next starts that same day; a day the app never runs is skipped. Settings and the last run live in
data/web/auto.json, so a restart never runs a day twice.
"""

from __future__ import annotations

import json
import logging
import threading
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator

log = logging.getLogger(__name__)


class AutoSettings(BaseModel):
    enabled: bool = False
    time: str = "08:00"  # local 24h time
    # hold: make the video and wait for approval in the app; publish: post to the targets right away
    mode: Literal["hold", "publish"] = "hold"
    targets: list[str] = Field(default_factory=list)  # empty = every enabled target in config
    dry_run: bool = False

    @field_validator("time")
    @classmethod
    def _hhmm(cls, v: str) -> str:
        h, m = (int(x) for x in v.split(":"))
        if not (0 <= h < 24 and 0 <= m < 60):
            raise ValueError("time must be HH:MM")
        return f"{h:02d}:{m:02d}"


class AutoState(BaseModel):
    last_run_date: str | None = None
    last_task: str | None = None
    last_job: str | None = None


class AutoStore:
    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()

    def load(self) -> tuple[AutoSettings, AutoState]:
        if not self.path.exists():
            return AutoSettings(), AutoState()
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        return AutoSettings.model_validate(raw.get("settings", {})), AutoState.model_validate(raw.get("state", {}))

    def save(self, settings: AutoSettings, state: AutoState) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps({"settings": settings.model_dump(), "state": state.model_dump()}, indent=2), encoding="utf-8")
            tmp.replace(self.path)


def next_run(settings: AutoSettings, state: AutoState, now: datetime | None = None) -> datetime | None:
    if not settings.enabled:
        return None
    now = now or datetime.now()
    h, m = (int(x) for x in settings.time.split(":"))
    today = now.replace(hour=h, minute=m, second=0, microsecond=0)
    if state.last_run_date == now.date().isoformat():
        return today + timedelta(days=1)
    return max(today, now) if now >= today else today


def due(settings: AutoSettings, state: AutoState, now: datetime | None = None) -> bool:
    now = now or datetime.now()
    nr = next_run(settings, state, now)
    return nr is not None and nr <= now


class AutoScheduler:
    """Checks every 20 s; hands a due run to ``submit`` (which queues it on the worker)."""

    def __init__(self, store: AutoStore, submit: Callable[[AutoSettings], tuple[str, str | None]]):
        self.store = store
        self.submit = submit
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, name="technews-auto", daemon=True)

    def start(self) -> None:
        if not self._thread.is_alive():
            self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def tick(self, now: datetime | None = None) -> bool:
        settings, state = self.store.load()
        if not due(settings, state, now):
            return False
        now = now or datetime.now()
        # Record the day before running, so a crash or restart mid-run never runs it twice.
        state.last_run_date = now.date().isoformat()
        task_id, _ = self.submit(settings)
        state.last_task = task_id
        self.store.save(settings, state)
        log.info("Auto mode: started today's run (task %s)", task_id)
        return True

    def _loop(self) -> None:
        while not self._stop.wait(20):
            try:
                self.tick()
            except Exception:
                log.exception("Auto mode check failed")
