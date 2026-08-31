"""Top-level orchestration: stems -> AnalysisResult."""
from __future__ import annotations

from pathlib import Path

from app.config import Settings, get_settings
from app.core.exceptions import AudioAnalysisError
from app.core.logging import get_logger

from .harmony import estimate_harmony
from .loader import load_audio, mix, slice_signal
from .melody import extract_melody
from .rhythm import estimate_rhythm
from .types import AnalysisResult, ChordEvent, NoteEvent

logger = get_logger(__name__)

# incoming stem key -> canonical role
_ALIASES = {
    "vocals": "vocal",
    "voice": "vocal",
    "lead": "vocal",
    "inst": "other",
    "instrumental": "other",
    "accompaniment": "other",
    "music": "other",
    "mixture": "mix",
    "mixed": "mix",
    "full": "mix",
}


def _canonical(stems: dict[str, Path]) -> dict[str, Path]:
    out: dict[str, Path] = {}
    for raw, path in stems.items():
        role = _ALIASES.get(raw.lower(), raw.lower())
        out.setdefault(role, Path(path))
    return out


def _parse_time_signature(time_signature: str) -> tuple[int, int]:
    try:
        num, den = time_signature.split("/")
        return int(num), int(den)
    except (IndexError, ValueError):
        return 4, 4


def _shift(events, offset: float):
    for e in events:
        e.start_sec += offset
        e.end_sec += offset
    return events


def analyze(
    stems: dict[str, Path],
    *,
    settings: Settings | None = None,
    window: tuple[float, float] | None = None,
) -> AnalysisResult:
    """Run the full melody + rhythm + harmony analysis over a set of stems.

    ``stems`` maps a role name (vocal / drums / bass / other, or a known alias)
    to an audio file path. ``window`` optionally restricts analysis to a
    (start_sec, end_sec) slice — used by the Step 4 measure-regeneration API.
    """
    settings = settings or get_settings()
    roles = _canonical(stems)
    if not roles:
        raise AudioAnalysisError("analyze() received no stems")

    sr = settings.analysis_sample_rate
    beats_per_bar, beat_unit = _parse_time_signature(settings.default_time_signature)

    # --- load audio -------------------------------------------------------- #
    loaded: dict[str, object] = {}
    offset = 0.0
    for role, path in roles.items():
        if role not in {"vocal", "drums", "bass", "other", "mix"}:
            continue
        y, _ = load_audio(path, sr)
        y, offset = slice_signal(y, sr, window)
        loaded[role] = y
    window_offset = offset if window else 0.0

    if "vocal" not in loaded and "mix" not in loaded:
        raise AudioAnalysisError(
            "Melody analysis needs a 'vocal' stem (or a 'mix').",
            detail={"received_roles": sorted(roles)},
        )

    # --- harmonic source (bass + other, else best available) ------------- #
    harmonic_parts = [loaded[r] for r in ("bass", "other") if r in loaded]
    if harmonic_parts:
        y_harmonic = mix(*harmonic_parts) if len(harmonic_parts) > 1 else harmonic_parts[0]
        harmonic_src = "+".join(r for r in ("bass", "other") if r in loaded)
    elif "mix" in loaded:
        y_harmonic, harmonic_src = loaded["mix"], "mix"
    elif "vocal" in loaded:
        y_harmonic, harmonic_src = loaded["vocal"], "vocal"
    else:
        raise AudioAnalysisError("No usable audio for harmonic analysis")

    y_vocal = loaded.get("vocal", loaded.get("mix"))
    y_drums = loaded.get("drums")

    duration = max(len(y) for y in loaded.values()) / sr

    # --- stages ---------------------------------------------------------- #
    grid, rhythm_engine = estimate_rhythm(
        y_harmonic, sr,
        y_drums=y_drums,
        prefer_backends=settings.prefer_backends,
        beats_per_bar=beats_per_bar,
        beat_unit=beat_unit,
    )
    key_name, chords, harmony_engine = estimate_harmony(
        y_harmonic, sr, grid,
        prefer_backends=settings.prefer_backends,
        change_min_beats=settings.chord_change_min_beats,
    )
    notes, melody_engine = extract_melody(
        y_vocal, sr,
        fmin_hz=settings.melody_fmin_hz,
        fmax_hz=settings.melody_fmax_hz,
        min_note_sec=settings.min_note_sec,
        prefer_backends=settings.prefer_backends,
    )

    # --- re-anchor to absolute time when a window was used -------------- #
    if window_offset:
        grid.beat_times = [t + window_offset for t in grid.beat_times]
        grid.downbeat_times = [t + window_offset for t in grid.downbeat_times]
        _shift(chords, window_offset)
        _shift(notes, window_offset)

    result = AnalysisResult(
        duration_sec=round(duration, 3),
        bpm=round(grid.bpm, 3),
        beat_times=[round(t, 4) for t in grid.beat_times],
        downbeat_times=[round(t, 4) for t in grid.downbeat_times],
        key=key_name,
        time_signature=grid.time_signature,
        notes=_dedupe_notes(notes),
        chords=_clean_chords(chords),
        backends={
            "rhythm": rhythm_engine,
            "harmony": harmony_engine,
            "melody": melody_engine,
            "harmonic_source": harmonic_src,
        },
        window_offset_sec=round(window_offset, 4),
    )
    logger.info("analysis done: %s", result.summary())
    return result


def _dedupe_notes(notes: list[NoteEvent]) -> list[NoteEvent]:
    seen: set[tuple[int, float]] = set()
    out: list[NoteEvent] = []
    for n in sorted(notes, key=lambda x: (x.start_sec, x.midi)):
        key = (n.midi, round(n.start_sec, 3))
        if key in seen:
            continue
        seen.add(key)
        n.start_sec = round(n.start_sec, 4)
        n.end_sec = round(max(n.end_sec, n.start_sec + 1e-3), 4)
        out.append(n)
    return out


def _clean_chords(chords: list[ChordEvent]) -> list[ChordEvent]:
    for c in chords:
        c.start_sec = round(c.start_sec, 4)
        c.end_sec = round(max(c.end_sec, c.start_sec + 1e-3), 4)
        c.confidence = round(c.confidence, 4)
    return chords
