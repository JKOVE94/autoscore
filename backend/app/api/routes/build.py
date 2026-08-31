"""Step 2 endpoint: assemble a lead-sheet MusicXML from a stored analysis."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.config import Settings, get_settings
from app.core.exceptions import ScoreValidationError
from app.schemas.jobs import BuildResponse
from app.services.audio_analyzer import AnalysisResult
from app.services.xml_builder import build_musicxml

router = APIRouter(prefix="/api", tags=["build"])


class BuildRequest(BaseModel):
    title: str | None = None


@router.post("/build/{job_id}", response_model=BuildResponse)
def build_job(
    job_id: str,
    body: BuildRequest | None = None,
    settings: Settings = Depends(get_settings),
) -> BuildResponse:
    out_dir = settings.outputs_path / Path(job_id).name
    analysis_path = out_dir / "analysis.json"
    if not analysis_path.is_file():
        raise ScoreValidationError(
            f"No analysis found for job {job_id}. Run POST /api/analyze/{job_id} first.",
            detail={"expected": str(analysis_path)},
        )

    try:
        data = json.loads(analysis_path.read_text(encoding="utf-8"))
        analysis = AnalysisResult.from_dict(data)
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise ScoreValidationError(f"Corrupt analysis.json for job {job_id}: {exc}") from exc

    result = build_musicxml(
        analysis,
        out_dir / "full.musicxml",
        settings=settings,
        title=(body.title if body else None),
    )
    return BuildResponse(
        job_id=job_id,
        musicxml_path=result.musicxml_path,
        measure_count=result.measure_count,
        note_count=result.note_count,
        rest_count=result.rest_count,
        chord_symbol_count=result.chord_symbol_count,
        dropped_notes=result.dropped_notes,
        warnings=result.warnings,
    )
