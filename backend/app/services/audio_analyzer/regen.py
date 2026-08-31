"""Step 4 support: re-analyse a subset of measures without re-tracking the beat.

The stored global beat grid (bpm, beat_times, downbeats) is kept as ground truth;
only melody + harmony extraction is re-run on the windowed audio, then re-quantised
against the same grid. Beat tracking on a ~2 s slice would be far less reliable.
"""
from __future__ import annotations

from pathlib import Path
from statistics import median

from app.config import Settings, get_settings
from app.core.exceptions import AudioAnalysisError
from app.core.logging import get_logger

from .harmony import estimate_harmony
from .loader import load_audio, mix, slice_signal
from .melody import extract_melody
from .types import AnalysisResult, BeatGrid, ChordEvent, NoteEvent

logger = get_logger(__name__)


def _parse_ts(ts: str) -> tuple[int, int]:
    try:
        n, d = ts.split("/")
        return int(n), int(d)
    except (ValueError, IndexError):
        return 4, 4


def _beat_period(beats: list[float]) -> float:
    diffs = [b - a for a, b in zip(beats, beats[1:], strict=False)]
    return median(diffs) if diffs else 0.5


def _beat_time(beats: list[float], period: float, idx: int) -> float:
    if idx < 0:
        return beats[0] + idx * period
    if idx < len(beats):
        return beats[idx]
    return beats[-1] + (idx - (len(beats) - 1)) * period


def measure_windows(analysis: AnalysisResult) -> list[tuple[float, float]]:
    """(t_start, t_end) in seconds for every measure, matching xml_builder's grid."""
    beats = analysis.beat_times
    if len(beats) < 2:
        return []
    num, _ = _parse_ts(analysis.time_signature)
    period = _beat_period(beats)
    last = analysis.duration_sec
    n_measures = 0
    while _beat_time(beats, period, n_measures * num) < last and n_measures < 4096:
        n_measures += 1
    return [
        (_beat_time(beats, period, i * num), _beat_time(beats, period, (i + 1) * num))
        for i in range(max(1, n_measures))
    ]


def selected_span(
    analysis: AnalysisResult, measure_numbers: list[int]
) -> tuple[float, float, list[int]]:
    """Enclosing (t_start, t_end) for 1-based ``measure_numbers`` + the valid list."""
    windows = measure_windows(analysis)
    if not windows:
        raise AudioAnalysisError("Analysis has no measures to regenerate")
    valid = sorted({m for m in measure_numbers if 1 <= m <= len(windows)})
    if not valid:
        raise AudioAnalysisError(
            f"No valid measure numbers in {measure_numbers}; score has {len(windows)} measures"
        )
    t0 = min(windows[m - 1][0] for m in valid)
    t1 = max(windows[m - 1][1] for m in valid)
    return t0, t1, valid


def analyze_window(
    stems: dict[str, Path],
    base: AnalysisResult,
    span: tuple[float, float],
    *,
    settings: Settings | None = None,
    min_note_sec: float | None = None,
    context_beats: float = 2.0,
) -> tuple[list[NoteEvent], list[ChordEvent]]:
    """Re-extract melody + harmony for ``span`` (absolute seconds) using base's grid."""
    settings = settings or get_settings()
    sr = settings.analysis_sample_rate
    num, den = _parse_ts(base.time_signature)
    period = _beat_period(base.beat_times)
    pad = context_beats * period

    load_win = (max(0.0, span[0] - pad), span[1] + pad)
    offset = max(0, round(load_win[0] * sr)) / sr

    roles: dict[str, object] = {}
    for raw, path in stems.items():
        role = {"vocals": "vocal", "inst": "other", "accompaniment": "other"}.get(
            raw.lower(), raw.lower()
        )
        if role not in {"vocal", "bass", "other", "drums", "mix"} or role in roles:
            continue
        y, _ = load_audio(path, sr)
        y, _ = slice_signal(y, sr, load_win)
        roles[role] = y

    if "vocal" not in roles and "mix" not in roles:
        raise AudioAnalysisError("Measure regeneration needs a 'vocal' stem (or 'mix')")

    harmonic_parts = [roles[r] for r in ("bass", "other") if r in roles]
    if harmonic_parts:
        y_harm = mix(*harmonic_parts) if len(harmonic_parts) > 1 else harmonic_parts[0]
    elif "mix" in roles:
        y_harm = roles["mix"]
    else:
        y_harm = roles["vocal"]
    y_vocal = roles["vocal"] if "vocal" in roles else roles["mix"]

    # grid restricted to the loaded window, shifted to slice-relative time
    rel_beats = [t - offset for t in base.beat_times if load_win[0] <= t <= load_win[1]]
    rel_downs = [t - offset for t in base.downbeat_times if load_win[0] <= t <= load_win[1]]
    if len(rel_beats) < 2:
        rel_beats = [0.0, period]
    grid = BeatGrid(base.bpm, rel_beats, rel_downs, beats_per_bar=num, beat_unit=den)

    notes, _ = extract_melody(
        y_vocal, sr,
        fmin_hz=settings.melody_fmin_hz,
        fmax_hz=settings.melody_fmax_hz,
        min_note_sec=(min_note_sec if min_note_sec is not None else settings.min_note_sec),
        prefer_backends=settings.prefer_backends,
    )
    _, chords, _ = estimate_harmony(
        y_harm, sr, grid,
        prefer_backends=settings.prefer_backends,
        change_min_beats=settings.chord_change_min_beats,
    )

    for n in notes:
        n.start_sec += offset
        n.end_sec += offset
    for c in chords:
        c.start_sec += offset
        c.end_sec += offset

    # keep only events whose onset lands inside the (unpadded) selection, with a
    # small grace at the leading edge so a note quantised just before the barline
    # is not lost to a few ms of jitter
    grace = 0.2 * period
    notes = [n for n in notes if span[0] - grace <= n.start_sec < span[1]]
    for n in notes:
        n.start_sec = max(n.start_sec, span[0])
    chords = [c for c in chords if span[0] <= (c.start_sec + c.end_sec) / 2 < span[1]]
    logger.info(
        "regen window %.2f-%.2fs -> %d notes, %d chords", span[0], span[1], len(notes), len(chords)
    )
    return notes, chords


def merge_window(
    base: AnalysisResult,
    new_notes: list[NoteEvent],
    new_chords: list[ChordEvent],
    span: tuple[float, float],
) -> AnalysisResult:
    """Return a copy of ``base`` with events inside ``span`` replaced."""
    t0, t1 = span
    kept_notes = [n for n in base.notes if n.end_sec <= t0 or n.start_sec >= t1]
    kept_chords = [c for c in base.chords if (c.start_sec + c.end_sec) / 2 <= t0
                   or (c.start_sec + c.end_sec) / 2 >= t1]

    merged = AnalysisResult(
        duration_sec=base.duration_sec,
        bpm=base.bpm,
        beat_times=list(base.beat_times),
        downbeat_times=list(base.downbeat_times),
        key=base.key,
        time_signature=base.time_signature,
        notes=sorted(kept_notes + new_notes, key=lambda n: n.start_sec),
        chords=sorted(kept_chords + new_chords, key=lambda c: c.start_sec),
        backends={**base.backends, "regen": "window"},
        window_offset_sec=base.window_offset_sec,
    )
    return merged
