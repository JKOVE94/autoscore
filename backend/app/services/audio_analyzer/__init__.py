"""Audio analysis pipeline (Step 2).

  * vocal  -> basic-pitch / librosa.pyin  -> melody note events
  * bass+other -> essentia / chroma templates -> BPM, beat grid, key, chords
  * drums  -> madmom / onset energy -> downbeat refinement

Public surface:
    analyze(stems, *, settings=None, window=None) -> AnalysisResult
    backend_status() -> dict         # which optional engines are available

Heavy deps (numpy/librosa/basic-pitch/essentia/madmom) are imported lazily, so
this package is safe to import even in a minimal environment.
"""
from __future__ import annotations

from .types import AnalysisResult, BeatGrid, ChordEvent, NoteEvent

__all__ = [
    "AnalysisResult",
    "BeatGrid",
    "ChordEvent",
    "NoteEvent",
    "analyze",
    "backend_status",
]


def analyze(*args, **kwargs) -> AnalysisResult:
    from .pipeline import analyze as _analyze

    return _analyze(*args, **kwargs)


def backend_status() -> dict:
    from .backends import status

    return status()
