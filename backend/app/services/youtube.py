"""Fetch audio from a video URL (YouTube etc.) via yt-dlp + ffmpeg.

Feeds input mode 1: the downloaded WAV is stored as the job's upload and then
flows through the normal separate → analyze → build chain.

Note: downloading third-party media may be subject to the source site's terms of
service and to copyright. This ingests whatever URL the operator supplies; using
it responsibly is the operator's responsibility.
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from app.config import Settings, get_settings
from app.core.exceptions import EngineNotConfiguredError, YouTubeError
from app.core.logging import get_logger

logger = get_logger(__name__)

_KEEP_EXTS = {".wav"}


@dataclass
class AudioFetchResult:
    path: Path
    title: str | None
    duration_sec: float | None
    source_url: str
    video_id: str | None


def validate_url(url: str, allowed_hosts: list[str]) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https"):
        raise YouTubeError("Only http(s) URLs are supported", detail={"url": url})
    host = (parsed.hostname or "").lower()
    if not host:
        raise YouTubeError("URL has no host", detail={"url": url})
    if allowed_hosts and host not in allowed_hosts:
        raise YouTubeError(
            f"Host not allowed: {host}",
            detail={"allowed_hosts": allowed_hosts},
        )
    return url.strip()


def engine_available() -> tuple[bool, str | None, str | None]:
    """(available, ytdlp_version, ffmpeg_path)."""
    ytdlp_version = None
    try:
        import yt_dlp  # noqa: PLC0415

        ytdlp_version = getattr(yt_dlp.version, "__version__", "unknown")
    except ImportError:
        return False, None, shutil.which("ffmpeg")
    return True, ytdlp_version, shutil.which(get_settings().ffmpeg_bin)


def _run_ytdlp(url: str, opts: dict) -> dict | None:
    """Isolated for testability — real network call lives here only."""
    import yt_dlp  # noqa: PLC0415

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=True)
    except yt_dlp.utils.DownloadError as exc:
        raise YouTubeError(f"Download failed: {exc}") from exc
    except yt_dlp.utils.YoutubeDLError as exc:  # pragma: no cover - broad yt-dlp errors
        raise YouTubeError(f"yt-dlp error: {exc}") from exc


def fetch_audio(
    url: str,
    dest_dir: Path,
    *,
    settings: Settings | None = None,
) -> AudioFetchResult:
    settings = settings or get_settings()
    if not settings.youtube_enabled:
        raise EngineNotConfiguredError("URL audio ingestion is disabled (YOUTUBE_ENABLED=false)")

    url = validate_url(url, settings.youtube_allowed_host_list)

    try:
        import yt_dlp  # noqa: F401, PLC0415
    except ImportError as exc:
        raise EngineNotConfiguredError(
            "yt-dlp is not installed. `pip install yt-dlp` (and ensure ffmpeg is on PATH)."
        ) from exc

    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    max_dur = settings.youtube_max_duration_sec

    def _reject_long(info: dict, *, incomplete: bool = False) -> str | None:  # noqa: ARG001
        dur = info.get("duration")
        if dur and dur > max_dur:
            return f"Video is {int(dur)}s; limit is {max_dur}s (YOUTUBE_MAX_DURATION_SEC)"
        return None

    opts: dict = {
        "format": "bestaudio/best",
        "outtmpl": str(dest_dir / "source.%(ext)s"),
        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "wav"}],
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "cachedir": False,
        "match_filter": _reject_long,
    }
    if shutil.which(settings.ffmpeg_bin):
        opts["ffmpeg_location"] = shutil.which(settings.ffmpeg_bin)

    logger.info("yt-dlp fetching %s", url)
    info = _run_ytdlp(url, opts)
    if info is None:
        raise YouTubeError("Nothing was downloaded (filtered out, private, or unavailable)")

    # keep only the extracted wav
    wavs: list[Path] = []
    for f in sorted(dest_dir.glob("*")):
        if f.is_file() and f.suffix.lower() in _KEEP_EXTS:
            wavs.append(f)
        elif f.is_file():
            f.unlink(missing_ok=True)

    if not wavs:
        raise YouTubeError(
            "Audio extraction produced no .wav — is ffmpeg installed and on PATH?"
        )

    wav = wavs[0]
    logger.info("yt-dlp ok: %s -> %s (%ss)", info.get("id"), wav.name, info.get("duration"))
    return AudioFetchResult(
        path=wav,
        title=info.get("title"),
        duration_sec=info.get("duration"),
        source_url=url,
        video_id=info.get("id"),
    )
