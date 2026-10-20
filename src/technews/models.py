"""Data saved in a job folder: the story, the script, and the voice track."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

VisualType = Literal["headline", "stat", "icon", "versus", "bullets", "outro"]
Trend = Literal["up", "down", "none"]


class Story(BaseModel):
    id: str
    title: str
    url: str
    source: str
    published: datetime | None = None
    summary: str = ""
    text: str = ""  # article body, when it could be fetched
    points: int = 0  # Hacker News
    comments: int = 0
    discussion_url: str = ""
    also_in: list[str] = Field(default_factory=list)  # other outlets covering the same story
    score: float = 0.0

    @property
    def context(self) -> str:
        """The text the script writer is allowed to draw facts from."""
        body = self.text.strip() or self.summary.strip()
        return body


class Visual(BaseModel):
    type: VisualType
    text: str = ""
    tag: str = ""
    value: str = ""
    label: str = ""
    trend: Trend = "none"
    icon: str = ""
    left: str = ""
    right: str = ""
    items: list[str] = Field(default_factory=list)

    def to_props(self) -> dict:
        """The shape video/src/types.ts expects."""
        t = self.type
        if t == "headline":
            return {"type": t, "text": self.text, **({"tag": self.tag} if self.tag else {})}
        if t == "stat":
            return {"type": t, "value": self.value, "label": self.label, "trend": self.trend}
        if t == "icon":
            return {"type": t, "icon": self.icon, "text": self.text}
        if t == "versus":
            return {"type": t, "left": self.left, "right": self.right, **({"label": self.label} if self.label else {})}
        if t == "bullets":
            return {"type": t, "items": self.items}
        return {"type": "outro", "text": self.text}


class ScriptScene(BaseModel):
    id: str
    narration: str
    visual: Visual


class Script(BaseModel):
    title: str
    topic: str
    description: str
    hashtags: list[str] = Field(default_factory=list)
    scenes: list[ScriptScene]
    llm: str = ""  # provider:model that wrote it
    warnings: list[str] = Field(default_factory=list)  # things to double-check before posting

    @property
    def word_count(self) -> int:
        return sum(len(s.narration.split()) for s in self.scenes)


class WordTiming(BaseModel):
    text: str
    startMs: int
    endMs: int


class SceneVoice(BaseModel):
    id: str
    audio: str  # relative to the job folder
    duration_s: float
    frames: int
    words: list[WordTiming]
    mouth: list[float]


class VoiceTrack(BaseModel):
    engine: str
    voice: str
    speed: float
    fps: int
    timed: bool  # True when word timings came from the model or an aligner, False when estimated
    scenes: list[SceneVoice]
    warnings: list[str] = Field(default_factory=list)  # takes that may skip or garble words

    @property
    def duration_s(self) -> float:
        return sum(s.frames for s in self.scenes) / self.fps
