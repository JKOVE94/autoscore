"""Step 4 endpoint: re-analyse selected measures and patch the score."""
from __future__ import annotations

import dataclasses
import json
from pathlib import Path

from fastapi import APIRouter, Depends

from app.config import Settings, get_settings
from app.core.exceptions import ScoreValidationError
from app.schemas.jobs import MeasureWindow, RegenerateRequest, RegenerateResponse
from app.services.audio_analyzer import (
    AnalysisResult,
    analyze_window,
    discover_stems,
    measure_windows,
    merge_window,
    selected_span,
)
from app.services.xml_builder import build_musicxml

router = APIRouter(prefix="/api", tags=["regenerate"])

# pitch_sensitivity 0..1 -> minimum note length (s): more sensitive = shorter blips kept
_MIN_NOTE_HI = 0.16
_MIN_NOTE_LO = 0.03


def _load_analysis(job_id: str, settings: Settings) -> tuple[AnalysisResult, Path]:
    out_dir = settings.outputs_path / Path(job_id).name
    path = out_dir / "analysis.json"
    if not path.is_file():
        raise ScoreValidationError(
            f"No analysis for job {job_id}. Run POST /api/analyze/{job_id} first."
        )
    try:
        return AnalysisResult.from_dict(json.loads(path.read_text(encoding="utf-8"))), out_dir
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise ScoreValidationError(f"Corrupt analysis.json for job {job_id}: {exc}") from exc


@router.get("/measures/{job_id}", response_model=list[MeasureWindow])
def list_measures(job_id: str, settings: Settings = Depends(get_settings)) -> list[MeasureWindow]:
    analysis, _ = _load_analysis(job_id, settings)
    return [
        MeasureWindow(number=i + 1, start_sec=round(t0, 3), end_sec=round(t1, 3))
        for i, (t0, t1) in enumerate(measure_windows(analysis))
    ]


@router.post("/regenerate-measure/{job_id}", response_model=RegenerateResponse)
def regenerate_measure(
    job_id: str,
    body: RegenerateRequest,
    settings: Settings = Depends(get_settings),
) -> RegenerateResponse:
    analysis, out_dir = _load_analysis(job_id, settings)
    stems = discover_stems(job_id, settings)
    if not stems:
        raise ScoreValidationError(f"No stems available for job {job_id}")

    t0, t1, valid = selected_span(analysis, body.measures)

    min_note_sec = None
    if body.pitch_sensitivity is not None:
        min_note_sec = _MIN_NOTE_HI - (_MIN_NOTE_HI - _MIN_NOTE_LO) * body.pitch_sensitivity

    new_notes, new_chords = analyze_window(
        stems, analysis, (t0, t1), settings=settings, min_note_sec=min_note_sec
    )
    merged = merge_window(analysis, new_notes, new_chords, (t0, t1))

    (out_dir / "analysis.json").write_text(
        json.dumps(dataclasses.asdict(merged), indent=2), encoding="utf-8"
    )
    result = build_musicxml(
        merged,
        out_dir / "full.musicxml",
        settings=settings,
        quantize_division=body.quantize_division,
    )
    musicxml = Path(result.musicxml_path).read_text(encoding="utf-8")

    return RegenerateResponse(
        job_id=job_id,
        changed_measures=valid,
        span_sec=(round(t0, 3), round(t1, 3)),
        measure_count=result.measure_count,
        note_count=result.note_count,
        chord_symbol_count=result.chord_symbol_count,
        musicxml=musicxml,
        warnings=result.warnings,
    )
