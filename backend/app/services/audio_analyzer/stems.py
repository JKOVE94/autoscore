"""Locate a job's stem audio files on disk."""
from __future__ import annotations

from pathlib import Path

from app.config import Settings
from app.core.media import AUDIO_EXTS


def discover_stems(job_id: str, settings: Settings) -> dict[str, Path]:
    """Stems from the separate step, else pre-split uploads. Keyed by file stem."""
    name = Path(job_id).name
    for base in (settings.stems_path / name, settings.uploads_path / name):
        if not base.is_dir():
            continue
        found: dict[str, Path] = {}
        for f in sorted(base.rglob("*")):
            if f.is_file() and f.suffix.lower() in AUDIO_EXTS:
                found.setdefault(f.stem.lower(), f)
        if found:
            return found
    return {}
