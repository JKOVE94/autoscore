"""Upload + dispatch endpoints for the three input modes."""
from __future__ import annotations

import shutil
from pathlib import Path

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
    """Store a single upload and infer the input mode from its media kind."""
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


@router.post("/upload-stems", response_model=UploadResponse)
async def upload_stems(
    files: list[UploadFile] = File(...),
    settings: Settings = Depends(get_settings),
) -> UploadResponse:
    """Input mode 2: store several pre-separated stem files under one job."""
    if not files:
        raise UnsupportedMediaError("No files supplied")
    job_id = new_job_id()
    dest_dir = settings.uploads_path / job_id
    stored: list[str] = []
    for f in files:
        if classify_extension(f.filename or "") != "audio":
            raise UnsupportedMediaError(f"{f.filename!r} is not an audio file")
        stored.append(str(await save_upload(f, dest_dir, max_mb=settings.max_upload_mb)))

    return UploadResponse(
        job_id=job_id,
        mode=InputMode.PRESPLIT_STEMS,
        kind="audio",
        stored_files=stored,
        message=f"Stored {len(stored)} stem(s). Next: POST /api/analyze/{job_id}.",
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
    result = omr_engine.run_omr(src, job_id, settings=settings)

    # Expose the OMR output under the same name the score/build flow uses so the
    # frontend can render it via GET /api/score/{job_id}.
    canonical = settings.outputs_path / Path(job_id).name / "full.musicxml"
    try:
        if Path(result.musicxml_path) != canonical:
            shutil.copyfile(result.musicxml_path, canonical)
    except OSError:
        pass
    return result


def _single_upload(job_id: str, settings: Settings) -> Path:
    job_dir = settings.uploads_path / Path(job_id).name
    files = [p for p in job_dir.glob("*") if p.is_file()] if job_dir.is_dir() else []
    if not files:
        raise UnsupportedMediaError(f"No upload found for job {job_id}")
    return files[0]
