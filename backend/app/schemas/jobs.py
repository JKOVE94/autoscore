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


class NoteEventOut(BaseModel):
    start_sec: float
    end_sec: float
    midi: int
    velocity: float
    confidence: float


class ChordEventOut(BaseModel):
    start_sec: float
    end_sec: float
    symbol: str
    root_pc: int | None = None
    quality: str | None = None
    confidence: float


class AnalysisResponse(BaseModel):
    job_id: str
    duration_sec: float
    bpm: float
    key: str
    time_signature: str
    beat_times: list[float]
    downbeat_times: list[float]
    notes: list[NoteEventOut]
    chords: list[ChordEventOut]
    backends: dict[str, str]
    window_offset_sec: float
    result_path: str | None = None


class BuildResponse(BaseModel):
    job_id: str
    musicxml_path: str
    measure_count: int
    note_count: int
    rest_count: int
    chord_symbol_count: int
    dropped_notes: int
    warnings: list[str] = Field(default_factory=list)


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
