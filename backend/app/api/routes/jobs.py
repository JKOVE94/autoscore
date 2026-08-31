"""Read-only endpoints for job artifacts (analysis JSON, generated MusicXML)."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse, JSONResponse

from app.config import Settings, get_settings
from app.core.exceptions import AutoScoreError

router = APIRouter(prefix="/api", tags=["jobs"])


class JobNotFoundError(AutoScoreError):
    status_code = 404
    code = "job_artifact_not_found"


def _job_name(job_id: str) -> str:
    return Path(job_id).name


@router.get("/jobs/{job_id}")
def job_status(job_id: str, settings: Settings = Depends(get_settings)) -> JSONResponse:
    name = _job_name(job_id)
    upload_dir = settings.uploads_path / name
    stem_dir = settings.stems_path / name
    out_dir = settings.outputs_path / name
    analysis = out_dir / "analysis.json"
    musicxml = out_dir / "full.musicxml"

    return JSONResponse(
        {
            "job_id": job_id,
            "has_upload": upload_dir.is_dir() and any(upload_dir.iterdir()),
            "has_stems": stem_dir.is_dir() and any(stem_dir.glob("*.wav")),
            "has_analysis": analysis.is_file(),
            "has_musicxml": musicxml.is_file(),
        }
    )


@router.get("/analysis/{job_id}")
def get_analysis(job_id: str, settings: Settings = Depends(get_settings)) -> JSONResponse:
    path = settings.outputs_path / _job_name(job_id) / "analysis.json"
    if not path.is_file():
        raise JobNotFoundError(f"No analysis for job {job_id}")
    return JSONResponse(json.loads(path.read_text(encoding="utf-8")))


@router.get("/score/{job_id}")
def get_score(job_id: str, settings: Settings = Depends(get_settings)) -> FileResponse:
    path = settings.outputs_path / _job_name(job_id) / "full.musicxml"
    if not path.is_file():
        raise JobNotFoundError(f"No MusicXML for job {job_id}. Run POST /api/build first.")
    return FileResponse(
        path,
        media_type="application/vnd.recordare.musicxml+xml",
        filename=f"{_job_name(job_id)}.musicxml",
    )
