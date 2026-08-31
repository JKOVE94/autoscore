"""Audio analysis pipeline (Step 2 — NOT YET IMPLEMENTED).

Planned responsibilities:
  * vocal.wav  -> basic-pitch  -> note on/off + pitch events
  * bass.wav + other.wav -> essentia / BTC -> BPM, beat grid, key, chord sequence
  * drums.wav  -> madmom / onset energy -> downbeat & section refinement

See docs/2026/2026.08.31/work-tracker.md rows #5.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class NoteEvent:
    start_sec: float
    end_sec: float
    midi: int
    velocity: float = 0.8


@dataclass
class ChordEvent:
    start_sec: float
    end_sec: float
    symbol: str  # e.g. "Cmaj7"


@dataclass
class AnalysisResult:
    bpm: float
    beat_times: list[float]
    downbeat_times: list[float]
    key: str
    time_signature: str
    notes: list[NoteEvent] = field(default_factory=list)
    chords: list[ChordEvent] = field(default_factory=list)


def analyze(stems: dict[str, Path]) -> AnalysisResult:
    raise NotImplementedError("audio_analyzer.analyze is implemented in Step 2")
