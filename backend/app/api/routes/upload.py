"""Upload + dispatch endpoints for the three input modes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile

from app.config import Settings, get_settings
from app.core.exceptions import UnsupportedMediaError
from app.core.media import classify_extension, new_job_id, save_upload
from app.schemas.jobs import (
    InputMode,
    OMRResult,
    StemSplitResult,
    UploadResponse,
)
from app.services import omr_engine, stem_splitter

router = APIRouter(prefix="/api", tags=["ingest"])


@router.post("/upload", response_model=UploadResponse)
async def upload(
    file: UploadFile = File(...),
    settings: Settings = Depends(get_settings),
) -> UploadResponse:
    """Store an upload and infer the input mode from its media kind."""
    kind = classify_extension(file.filename or "")
    job_id = new_job_id()
    dest_dir = settings.uploads_path / job_id
    stored = await save_upload(file, dest_dir, max_mb=settings.max_upload_mb)

    mode = InputMode.SINGLE_AUDIO if kind == "audio" else InputMode.SCORE_IMAGE
    next_step = "separate" if kind == "audio" else "omr"
    return UploadResponse(
        job_id=job_id,
        mode=mode,
        kind=kind,
        stored_files=[str(stored)],
        message=f"Stored {stored.name}. Next: POST /api/{next_step}/{job_id}.",
    )


@router.post("/separate/{job_id}", response_model=StemSplitResult)
def separate(job_id: str, settings: Settings = Depends(get_settings)) -> StemSplitResult:
    """Input mode 1: split the uploaded mixed audio into stems via Stemdeck."""
    src = _single_upload(job_id, settings)
    if classify_extension(src.name) != "audio":
        raise UnsupportedMediaError("Job upload is not an audio file")
    return stem_splitter.split_audio(src, job_id, settings=settings)


@router.post("/omr/{job_id}", response_model=OMRResult)
def omr(job_id: str, settings: Settings = Depends(get_settings)) -> OMRResult:
    """Input mode 3: run Audiveris OMR on the uploaded score image."""
    src = _single_upload(job_id, settings)
    if classify_extension(src.name) != "image":
        raise UnsupportedMediaError("Job upload is not a score image")
    return omr_engine.run_omr(src, job_id, settings=settings)


def _single_upload(job_id: str, settings: Settings):
    from pathlib import Path

    job_dir = settings.uploads_path / Path(job_id).name
    files = [p for p in job_dir.glob("*") if p.is_file()] if job_dir.is_dir() else []
    if not files:
        raise UnsupportedMediaError(f"No upload found for job {job_id}")
    return files[0]
