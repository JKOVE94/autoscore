"""Step 5 endpoint: compress a full score into a repeat-based lead sheet."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from app.config import Settings, get_settings
from app.core.exceptions import AutoScoreError, ScoreValidationError
from app.schemas.jobs import CompressResponse
from app.services.audio_analyzer import AnalysisResult
from app.services.form_compressor import compress_musicxml

router = APIRouter(prefix="/api", tags=["compress"])


class _NotFound(AutoScoreError):
    status_code = 404
    code = "artifact_not_found"


def _job_dir(job_id: str, settings: Settings) -> Path:
    return settings.outputs_path / Path(job_id).name


@router.post("/compress/{job_id}", response_model=CompressResponse)
def compress_job(job_id: str, settings: Settings = Depends(get_settings)) -> CompressResponse:
    out_dir = _job_dir(job_id, settings)
    src = out_dir / "full.musicxml"
    if not src.is_file():
        raise ScoreValidationError(
            f"No score for job {job_id}. Run POST /api/build/{job_id} first."
        )

    analysis: AnalysisResult | None = None
    analysis_path = out_dir / "analysis.json"
    if analysis_path.is_file():
        try:
            analysis = AnalysisResult.from_dict(
                json.loads(analysis_path.read_text(encoding="utf-8"))
            )
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            analysis = None

    dest = out_dir / "lead_sheet.musicxml"
    report = compress_musicxml(src, dest, analysis=analysis, settings=settings)

    return CompressResponse(
        job_id=job_id,
        musicxml_path=str(dest),
        musicxml=dest.read_text(encoding="utf-8"),
        original_measures=report.original_measures,
        compressed_measures=report.compressed_measures,
        operations=report.operations,
        song_form=report.song_form,
    )


@router.get("/lead-sheet/{job_id}")
def get_lead_sheet(job_id: str, settings: Settings = Depends(get_settings)) -> FileResponse:
    path = _job_dir(job_id, settings) / "lead_sheet.musicxml"
    if not path.is_file():
        raise _NotFound(f"No lead sheet for job {job_id}. Run POST /api/compress first.")
    return FileResponse(
        path,
        media_type="application/vnd.recordare.musicxml+xml",
        filename=f"{Path(job_id).name}-lead-sheet.musicxml",
    )
