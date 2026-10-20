"""Publisher interface + token storage (ported from Clip Creator, without the database)."""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from ..config import CONFIG_DIR, load_config

log = logging.getLogger(__name__)


class PublishError(RuntimeError):
    """Permanent failure (bad credentials, rejected video)."""


class RetryLater(RuntimeError):
    """Transient failure (quota, rate limit, still processing)."""


@dataclass
class PostRequest:
    video: Path
    title: str
    description: str
    hashtags: list[str]
    privacy: str = "private"
    mode: str = ""  # tiktok: inbox_draft | direct
    ai_generated: bool = True
    extra: dict = field(default_factory=dict)


@dataclass
class PostResult:
    remote_id: str
    url: str = ""
    status: str = "published"  # published | processing | needs_action
    state: dict | None = None


class Publisher(ABC):
    platform = "base"

    def __init__(self, account_id: str):
        self.account_id = account_id

    @abstractmethod
    def publish(self, req: PostRequest) -> PostResult: ...

    def check(self, state: dict) -> PostResult | None:
        """Poll an in-progress post. Return None while still processing."""
        return None


def secrets_dir() -> Path:
    d = load_config().paths.data / "secrets"
    d.mkdir(parents=True, exist_ok=True)
    return d


def token_path(platform: str, account_id: str) -> Path:
    return secrets_dir() / f"{platform}_{account_id or 'main'}.json"


def load_token(platform: str, account_id: str) -> dict | None:
    p = token_path(platform, account_id)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return None


def save_token(platform: str, account_id: str, data: dict) -> None:
    p = token_path(platform, account_id)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1), encoding="utf-8")
    tmp.replace(p)


def client_secret_path(platform: str) -> Path:
    return CONFIG_DIR / "secrets" / f"{platform}_client_secret.json"
