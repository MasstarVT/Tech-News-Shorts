"""Configuration models.

Settings come from ``config/config.yaml`` (copy of ``config/config.example.yaml``) and fall back to the
defaults below. Secrets (API keys, webhook URLs) never live in YAML; they come from the environment /
``.env`` and are referenced by env-var name.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = PROJECT_ROOT / "config"


# --------------------------------------------------------------------------- paths


class PathsConfig(BaseModel):
    data_dir: Path = Path("data")
    output_dir: Path = Path("out")
    video_dir: Path = Path("video")
    assets_dir: Path = Path("assets")

    def resolve(self, p: Path) -> Path:
        return p if p.is_absolute() else PROJECT_ROOT / p

    @property
    def data(self) -> Path:
        return self.resolve(self.data_dir)

    @property
    def output(self) -> Path:
        return self.resolve(self.output_dir)

    @property
    def video(self) -> Path:
        return self.resolve(self.video_dir)

    @property
    def assets(self) -> Path:
        return self.resolve(self.assets_dir)


# --------------------------------------------------------------------------- channel look


class BrandConfig(BaseModel):
    name: str = "Byte Brief"
    # Optional colour overrides for the video (keys: bg, bgDeep, line, draft, accent, alert, ink).
    theme: dict[str, str] = Field(default_factory=dict)
    outro_text: str = "Follow for tomorrow's brief"


# --------------------------------------------------------------------------- news


class FeedConfig(BaseModel):
    name: str
    url: str
    weight: float = 1.0


def _default_feeds() -> list[FeedConfig]:
    return [
        FeedConfig(name="The Verge", url="https://www.theverge.com/rss/index.xml"),
        FeedConfig(name="Ars Technica", url="https://feeds.arstechnica.com/arstechnica/index"),
        FeedConfig(name="TechCrunch", url="https://techcrunch.com/feed/"),
        FeedConfig(name="Engadget", url="https://www.engadget.com/rss.xml"),
        FeedConfig(name="Wired", url="https://www.wired.com/feed/rss", weight=0.9),
        FeedConfig(name="9to5Mac", url="https://9to5mac.com/feed/", weight=0.8),
        FeedConfig(name="9to5Google", url="https://9to5google.com/feed/", weight=0.8),
    ]


class HackerNewsConfig(BaseModel):
    enabled: bool = True
    min_points: int = 150
    max_items: int = 30
    weight: float = 1.0


class NewsConfig(BaseModel):
    feeds: list[FeedConfig] = Field(default_factory=_default_feeds)
    hacker_news: HackerNewsConfig = Field(default_factory=HackerNewsConfig)
    max_age_hours: float = 36.0
    # Fetch the article page for the full text (much better scripts than the feed summary alone).
    fetch_article: bool = True
    # Stories whose title contains any of these are skipped (shopping posts, sponsored content...).
    exclude_keywords: list[str] = Field(
        default_factory=lambda: [
            "deals", "deal alert", "best deal", "lowest price", "% off", "on sale", "coupon", "promo code",
            "discount code", "sponsored", "gift guide", "prime day", "black friday", "cyber monday",
            "how to watch", "wordle", "connections hints", "best vpn",
        ]
    )
    # Extra score for titles mentioning these (case-insensitive).
    boost_keywords: dict[str, float] = Field(
        default_factory=lambda: {
            "ai": 0.25, "openai": 0.3, "nvidia": 0.3, "apple": 0.25, "google": 0.2, "microsoft": 0.2,
            "tesla": 0.2, "spacex": 0.2, "iphone": 0.2, "android": 0.15, "chip": 0.15, "gpu": 0.2,
            "security": 0.15, "hack": 0.2, "breach": 0.2, "launch": 0.1, "game": 0.1, "playstation": 0.15,
            "xbox": 0.15, "nintendo": 0.2, "steam": 0.15, "anthropic": 0.2, "meta": 0.15, "robot": 0.15,
        }
    )
    # Don't cover a story that looks like one covered within this many days.
    repeat_window_days: int = 14
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) TechNewsShorts/0.1"
    timeout_s: float = 20.0


# --------------------------------------------------------------------------- LLM


class LLMProviderConfig(BaseModel):
    enabled: bool = True
    api_key_env: str | None = None
    base_url: str | None = None


class LLMTaskRoute(BaseModel):
    provider: str = "null"
    model: str = ""
    # Not every model accepts sampling params (e.g. current Claude models reject temperature);
    # leave unset unless the chosen model supports it.
    temperature: float | None = None
    # Reasoning effort for providers that support it (Claude: low|medium|high|xhigh|max;
    # OpenAI reasoning models: low|medium|high; Ollama: "none" turns thinking off).
    effort: str | None = None
    max_tokens: int = 4000

    @field_validator("provider", mode="before")
    @classmethod
    def _yaml_null(cls, v: object) -> object:
        return "null" if v is None else v  # `provider: null` in YAML parses as None


def _default_providers() -> dict[str, LLMProviderConfig]:
    return {
        "null": LLMProviderConfig(),
        "ollama": LLMProviderConfig(base_url="http://127.0.0.1:11434"),
        "anthropic": LLMProviderConfig(api_key_env="ANTHROPIC_API_KEY"),
        "openai": LLMProviderConfig(api_key_env="OPENAI_API_KEY"),
        "gemini": LLMProviderConfig(api_key_env="GEMINI_API_KEY"),
    }


def _default_tasks() -> dict[str, LLMTaskRoute]:
    return {"script": LLMTaskRoute(provider="ollama", model="qwen3:14b", temperature=0.6)}


class LLMConfig(BaseModel):
    providers: dict[str, LLMProviderConfig] = Field(default_factory=_default_providers)
    tasks: dict[str, LLMTaskRoute] = Field(default_factory=_default_tasks)
    budget_usd_per_video: float = 0.50
    # Optional per-model pricing (USD per million tokens) used for the cost log.
    pricing: dict[str, tuple[float, float]] = Field(default_factory=dict)


# --------------------------------------------------------------------------- script


class ScriptConfig(BaseModel):
    # Spoken words for the whole video, outro included. ~150 words/min at speed 1.15 -> 35-50 s.
    min_words: int = 80
    max_words: int = 135
    min_scenes: int = 3
    max_scenes: int = 6  # not counting the outro
    # Extra direction for the writer, e.g. "Dry humour, explain jargon in plain words".
    style: str = "Upbeat and clear. Explain jargon in plain words. No hype words like 'insane' or 'game-changer'."
    # Stat visuals whose number doesn't appear in the source text are swapped for a headline.
    verify_numbers: bool = True


# --------------------------------------------------------------------------- voice


DEFAULT_PRONUNCIATIONS: dict[str, str] = {
    "vs": "versus", "vs.": "versus", "AR": "A R", "EV": "E V", "EVs": "E Vees", "IPO": "I P O",
    "IPOs": "I P Os", "U.S.": "U S", "U.K.": "U K", "E.U.": "E U", "SaaS": "sass",
    "Xiaomi": "shao-mee", "Huawei": "wah-way", "GPUs": "G P Use", "CPUs": "C P Use",
    "NPUs": "N P Use", "LLMs": "L L Ems", "RAM": "ram", "ROM": "rom", "SIM": "sim",
}


class VoiceConfig(BaseModel):
    engine: Literal["kokoro"] = "kokoro"
    voice: str = "af_heart"
    speed: float = 1.15
    lang: str = "en-us"
    model_url: str = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/kokoro-v1.0.onnx"
    voices_url: str = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/voices-v1.0.bin"
    lead_in_s: float = 0.12
    scene_tail_s: float = 0.30
    outro_tail_s: float = 1.0
    # Extra words the voice gets wrong -> how to say them (whole words, case-sensitive). These are added to
    # DEFAULT_PRONUNCIATIONS. Numbers, money ($5B), multipliers (3x) and units (120Hz) are handled automatically.
    pronunciations: dict[str, str] = Field(default_factory=dict, validate_default=True)

    @field_validator("pronunciations", mode="after")
    @classmethod
    def _merge_defaults(cls, v: dict[str, str]) -> dict[str, str]:
        return {**DEFAULT_PRONUNCIATIONS, **v}


# --------------------------------------------------------------------------- render


class CaptionConfig(BaseModel):
    enabled: bool = True
    max_words: int = 3
    max_chars: int = 16


class RenderConfig(BaseModel):
    fps: int = 30
    crf: int = 23  # flat graphics stay crisp; keeps a 40 s short under Discord's 10 MB webhook limit
    concurrency: str | None = None  # e.g. "8" or "50%"; Remotion picks a default when unset
    # Path to chrome-headless-shell. Unset: Remotion downloads one on first render.
    browser_executable: str | None = None
    gl: str | None = None  # "angle" can speed up rendering on Windows with a GPU
    captions: CaptionConfig = Field(default_factory=CaptionConfig)
    sfx: bool = True
    # Optional background music: put tracks you have the rights to in this folder (mp3/wav/ogg/m4a).
    music_dir: Path = Path("assets/music")
    music_volume: float = 0.07


# --------------------------------------------------------------------------- publish


class PublishTarget(BaseModel):
    platform: Literal["export", "youtube", "tiktok"]
    enabled: bool = True
    account: str = "main"
    privacy: Literal["public", "unlisted", "private"] = "private"
    mode: Literal["inbox_draft", "direct"] = "inbox_draft"  # tiktok only


def _default_targets() -> list[PublishTarget]:
    return [
        PublishTarget(platform="export"),
        PublishTarget(platform="youtube", enabled=False),
        PublishTarget(platform="tiktok", enabled=False),
    ]


class PublishConfig(BaseModel):
    targets: list[PublishTarget] = Field(default_factory=_default_targets)
    # Where the export target copies finished videos. Point it at a OneDrive/Google Drive folder
    # to get videos onto your phone for posting.
    export_dir: Path = Path("out/exports")
    discord_webhook_env: str = "DISCORD_WEBHOOK_URL"
    youtube_category_id: str = "28"  # Science & Technology
    youtube_synthetic_media: bool = False  # animated graphics aren't "realistic altered content"
    tiktok_ai_label: bool = True


# --------------------------------------------------------------------------- root


class AppConfig(BaseModel):
    paths: PathsConfig = Field(default_factory=PathsConfig)
    brand: BrandConfig = Field(default_factory=BrandConfig)
    news: NewsConfig = Field(default_factory=NewsConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    script: ScriptConfig = Field(default_factory=ScriptConfig)
    voice: VoiceConfig = Field(default_factory=VoiceConfig)
    render: RenderConfig = Field(default_factory=RenderConfig)
    publish: PublishConfig = Field(default_factory=PublishConfig)


def _read_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


@lru_cache(maxsize=1)
def load_config(path: str | None = None) -> AppConfig:
    load_dotenv(PROJECT_ROOT / ".env", override=False)
    cfg_path = Path(path) if path else Path(os.environ.get("TECHNEWS_CONFIG", CONFIG_DIR / "config.yaml"))
    if cfg_path.exists():
        return AppConfig.model_validate(_read_yaml(cfg_path))
    return AppConfig()


def secret(env_name: str | None) -> str | None:
    """Look up a secret by env-var name (``.env`` is loaded by ``load_config``)."""
    if not env_name:
        return None
    load_dotenv(PROJECT_ROOT / ".env", override=False)
    val = os.environ.get(env_name)
    return val or None
