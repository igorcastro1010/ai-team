"""Bounded shared video document. No paths, URLs, arbitrary fonts or filters."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class SceneInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(default="", max_length=240)
    duration: int = Field(default=5, ge=1, le=20, strict=True)
    media_id: UUID | None = None
    x: float = Field(default=50, ge=0, le=100, allow_inf_nan=False)
    y: float = Field(default=50, ge=0, le=100, allow_inf_nan=False)
    font_size: int = Field(default=36, ge=18, le=96, strict=True)
    color: str = Field(default="#ffffff", pattern=r"^#[0-9a-fA-F]{6}$")
    background: str = Field(default="#13233c", pattern=r"^#[0-9a-fA-F]{6}$")
    font: Literal["sans", "serif", "mono"] = "sans"
    animation: Literal["none", "fade", "zoom", "pan"] = "none"
    text_animation: Literal["none", "fade", "slide"] = "none"
    transition: Literal["cut", "fade"] = "cut"

    @field_validator("text")
    @classmethod
    def readable(cls, value):
        if any(ord(c) < 32 and c != "\n" for c in value):
            raise ValueError("Texto inválido")
        return value.strip()


class AudioInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    media_id: UUID
    volume: float = Field(default=0.5, ge=0, le=1, allow_inf_nan=False)
    fade_in: float = Field(default=0.4, ge=0, le=3, allow_inf_nan=False)
    fade_out: float = Field(default=0.4, ge=0, le=3, allow_inf_nan=False)


class StudioDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=120)
    format: Literal["vertical", "square", "horizontal"] = "vertical"
    resolution: Literal["720p", "1080p"] = "720p"
    scenes: list[SceneInput] = Field(min_length=1, max_length=6)
    audio: AudioInput | None = None

    @model_validator(mode="after")
    def bounded(self):
        if sum(scene.duration for scene in self.scenes) > 60 or not self.title.strip():
            raise ValueError("Use até60 segundos e informe um título")
        return self
