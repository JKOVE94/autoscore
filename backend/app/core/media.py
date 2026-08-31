"""Upload validation and safe file persistence helpers."""
from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from fastapi import UploadFile

from app.core.exceptions import UnsupportedMediaError, UploadTooLargeError

AUDIO_EXTS = {".wav", ".mp3", ".flac", ".m4a", ".aiff", ".aif"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".pdf", ".bmp"}

InputKind = str  # "audio" | "image"


def classify_extension(filename: str) -> InputKind:
    ext = Path(filename).suffix.lower()
    if ext in AUDIO_EXTS:
        return "audio"
    if ext in IMAGE_EXTS:
        return "image"
    raise UnsupportedMediaError(
        f"Unsupported file type: {ext or '(none)'}",
        detail={"audio": sorted(AUDIO_EXTS), "image": sorted(IMAGE_EXTS)},
    )


def new_job_id() -> str:
    return uuid.uuid4().hex[:12]


async def save_upload(upload: UploadFile, dest_dir: Path, *, max_mb: int) -> Path:
    """Stream an upload to disk, enforcing the size limit as we go."""
    if not upload.filename:
        raise UnsupportedMediaError("Missing filename on upload")

    dest_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(upload.filename).name
    dest = dest_dir / safe_name

    max_bytes = max_mb * 1024 * 1024
    written = 0
    try:
        with dest.open("wb") as fh:
            while chunk := await upload.read(1024 * 1024):
                written += len(chunk)
                if written > max_bytes:
                    fh.close()
                    dest.unlink(missing_ok=True)
                    raise UploadTooLargeError(f"Upload exceeds {max_mb} MB limit")
                fh.write(chunk)
    finally:
        await upload.close()

    if written == 0:
        dest.unlink(missing_ok=True)
        raise UnsupportedMediaError("Uploaded file is empty")

    return dest


def clear_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)
