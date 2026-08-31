"""API request/response models."""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class InputMode(str, Enum):
    SINGLE_AUDIO = "single_audio"      # mode 1: one mixed file -> stemdeck split
    PRESPLIT_STEMS = "presplit_stems"  # mode 2: already-separated stems
    SCORE_IMAGE = "score_image"        # mode 3: sheet-music image -> OMR


class StemTrack(BaseModel):
    name: str
    path: str
    duration_sec: float | None = None


class StemSplitResult(BaseModel):
    job_id: str
    engine: str
    source: str
    tracks: list[StemTrack]
    elapsed_sec: float


class OMRResult(BaseModel):
    job_id: str
    source: str
    musicxml_path: str
    measure_count: int
    part_count: int
    warnings: list[str] = Field(default_factory=list)
    elapsed_sec: float


class UploadResponse(BaseModel):
    job_id: str
    mode: InputMode
    kind: str
    stored_files: list[str]
    message: str


class EngineStatus(BaseModel):
    name: str
    configured: bool
    executable: str | None = None
    version: str | None = None
    detail: str | None = None


class HealthResponse(BaseModel):
    status: str
    app_env: str
    engines: list[EngineStatus]
