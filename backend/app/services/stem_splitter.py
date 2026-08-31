"""Stemdeck integration wrapper (input mode 1).

Wraps the Stemdeck CLI (https://github.com/stemdeckapp/stemdeck) to split a single
mixed audio file into `vocal`, `drums`, `bass`, `other` stems using Apple Silicon
CoreML acceleration. Falls back to `demucs` when configured and Stemdeck is absent.
"""
from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path

from app.config import Settings, get_settings
from app.core.exceptions import EngineNotConfiguredError, StemSeparationError
from app.core.logging import get_logger
from app.schemas.jobs import StemSplitResult, StemTrack

logger = get_logger(__name__)

CANONICAL_STEMS = ("vocal", "drums", "bass", "other")
# Stemdeck / demucs sometimes emit "vocals"; normalise to our canonical names.
_ALIASES = {"vocals": "vocal", "voice": "vocal", "accompaniment": "other", "piano": "other"}
_AUDIO_OUT_EXTS = (".wav", ".flac", ".mp3")


def _resolve_bin(name: str) -> str | None:
    if not name:
        return None
    p = Path(name)
    if p.is_file():
        return str(p)
    return shutil.which(name)


def engine_available(settings: Settings | None = None) -> tuple[bool, str, str | None]:
    """Return (available, engine_name, resolved_path)."""
    settings = settings or get_settings()
    stemdeck = _resolve_bin(settings.stemdeck_bin)
    if stemdeck:
        return True, "stemdeck", stemdeck
    if settings.stem_fallback == "demucs":
        demucs = _resolve_bin("demucs")
        if demucs:
            return True, "demucs", demucs
    return False, "stemdeck", None


def probe_version(settings: Settings | None = None) -> str | None:
    settings = settings or get_settings()
    resolved = _resolve_bin(settings.stemdeck_bin)
    if not resolved:
        return None
    for flag in ("--version", "version", "-v"):
        try:
            out = subprocess.run(
                [resolved, flag], capture_output=True, text=True, timeout=15
            )
            if out.returncode == 0 and out.stdout.strip():
                return out.stdout.strip().splitlines()[0]
        except (OSError, subprocess.SubprocessError):
            continue
    return None


def _normalise_stem_name(raw: str) -> str | None:
    key = raw.lower()
    key = _ALIASES.get(key, key)
    return key if key in CANONICAL_STEMS else None


def _collect_stems(out_dir: Path) -> dict[str, Path]:
    found: dict[str, Path] = {}
    for path in sorted(out_dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in _AUDIO_OUT_EXTS:
            continue
        name = _normalise_stem_name(path.stem)
        if name and name not in found:
            found[name] = path
    return found


def _run_stemdeck(exe: str, src: Path, out_dir: Path, extra_args: list[str], timeout: int) -> None:
    cmd = [exe, "separate", "--input", str(src), "--output", str(out_dir), *extra_args]
    logger.info("stemdeck: %s", " ".join(cmd))
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:  # pragma: no cover - env dependent
        raise StemSeparationError("Stemdeck timed out", detail={"timeout_sec": timeout}) from exc
    except OSError as exc:  # pragma: no cover - env dependent
        raise StemSeparationError(f"Failed to launch Stemdeck: {exc}") from exc
    if proc.returncode != 0:
        raise StemSeparationError(
            "Stemdeck exited with an error",
            detail={"returncode": proc.returncode, "stderr": proc.stderr[-2000:]},
        )


def _run_demucs(exe: str, src: Path, out_dir: Path, timeout: int) -> None:  # pragma: no cover
    cmd = [exe, "-n", "htdemucs", "--out", str(out_dir), str(src)]
    logger.info("demucs fallback: %s", " ".join(cmd))
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as exc:
        raise StemSeparationError(f"demucs fallback failed: {exc}") from exc
    if proc.returncode != 0:
        raise StemSeparationError(
            "demucs exited with an error",
            detail={"returncode": proc.returncode, "stderr": proc.stderr[-2000:]},
        )


def split_audio(
    source: Path,
    job_id: str,
    *,
    settings: Settings | None = None,
    timeout: int | None = None,
) -> StemSplitResult:
    """Split ``source`` into canonical stems. Raises AutoScoreError subclasses on failure."""
    settings = settings or get_settings()
    source = Path(source)
    if not source.is_file():
        raise StemSeparationError(f"Source audio not found: {source}")

    available, engine, exe = engine_available(settings)
    if not available or exe is None:
        raise EngineNotConfiguredError(
            "Stemdeck is not configured. Set STEMDECK_BIN or enable STEM_FALLBACK=demucs.",
            detail={"stemdeck_bin": settings.stemdeck_bin, "fallback": settings.stem_fallback},
        )

    out_dir = settings.stems_path / job_id
    out_dir.mkdir(parents=True, exist_ok=True)
    run_timeout = timeout or settings.omr_timeout

    started = time.perf_counter()
    if engine == "stemdeck":
        _run_stemdeck(exe, source, out_dir, settings.stemdeck_arg_list, run_timeout)
    else:
        _run_demucs(exe, source, out_dir, run_timeout)
    elapsed = time.perf_counter() - started

    stems = _collect_stems(out_dir)
    missing = [s for s in CANONICAL_STEMS if s not in stems]
    if missing:
        raise StemSeparationError(
            "Separation finished but expected stems are missing",
            detail={"missing": missing, "found": sorted(stems)},
        )

    tracks = [
        StemTrack(name=name, path=str(stems[name]))
        for name in CANONICAL_STEMS
    ]
    logger.info("stem split ok job=%s engine=%s elapsed=%.1fs", job_id, engine, elapsed)
    return StemSplitResult(
        job_id=job_id,
        engine=engine,
        source=str(source),
        tracks=tracks,
        elapsed_sec=round(elapsed, 2),
    )
