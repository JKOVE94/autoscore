"""Dataclasses shared across the audio-analysis pipeline.

Kept dependency-free (pure stdlib) so the package imports even when numpy /
librosa / basic-pitch are not installed.
"""
from __future__ import annotations

from dataclasses import dataclass, field

NO_CHORD = "N.C."


@dataclass
class NoteEvent:
    """A single melodic note in wall-clock seconds."""

    start_sec: float
    end_sec: float
    midi: int
    velocity: float = 0.8
    confidence: float = 1.0

    @property
    def duration_sec(self) -> float:
        return max(0.0, self.end_sec - self.start_sec)


@dataclass
class ChordEvent:
    start_sec: float
    end_sec: float
    symbol: str  # "C", "Am", "G7", "Fmaj7", "N.C."
    root_pc: int | None = None  # pitch class 0-11 (C=0), None for N.C.
    quality: str | None = None  # "maj", "min", "dom7", ...
    confidence: float = 1.0

    @property
    def duration_sec(self) -> float:
        return max(0.0, self.end_sec - self.start_sec)


@dataclass
class BeatGrid:
    bpm: float
    beat_times: list[float]
    downbeat_times: list[float]
    beats_per_bar: int = 4
    beat_unit: int = 4  # denominator of the time signature

    @property
    def time_signature(self) -> str:
        return f"{self.beats_per_bar}/{self.beat_unit}"


@dataclass
class AnalysisResult:
    duration_sec: float
    bpm: float
    beat_times: list[float]
    downbeat_times: list[float]
    key: str  # e.g. "C major", "A minor"
    time_signature: str  # e.g. "4/4"
    notes: list[NoteEvent] = field(default_factory=list)
    chords: list[ChordEvent] = field(default_factory=list)
    backends: dict[str, str] = field(default_factory=dict)  # stage -> engine name
    window_offset_sec: float = 0.0  # >0 when only a slice was analysed (Step 4)

    def summary(self) -> dict:
        return {
            "duration_sec": round(self.duration_sec, 2),
            "bpm": round(self.bpm, 2),
            "key": self.key,
            "time_signature": self.time_signature,
            "n_beats": len(self.beat_times),
            "n_downbeats": len(self.downbeat_times),
            "n_notes": len(self.notes),
            "n_chords": len(self.chords),
            "backends": self.backends,
        }
