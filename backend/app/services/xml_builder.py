"""MusicXML builder (Step 2 — NOT YET IMPLEMENTED).

Planned responsibilities:
  * quantize note events onto the beat grid (16th-note resolution)
  * place chord symbols on the harmony/top staff, melody on the bottom staff
  * assemble a valid .musicxml via music21 and write it to storage/outputs/<job_id>/

See docs/2026/2026.08.31/work-tracker.md row #6.
"""
from __future__ import annotations

from pathlib import Path

from app.services.audio_analyzer import AnalysisResult


def build_musicxml(analysis: AnalysisResult, out_path: Path) -> Path:
    raise NotImplementedError("xml_builder.build_musicxml is implemented in Step 2")
