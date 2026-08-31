"""MusicXML builder (Step 2).

Turns an :class:`AnalysisResult` into a valid lead-sheet ``.musicxml``:

  * quantise melody notes onto the analysed beat grid (configurable resolution,
    default sixteenth-note)
  * lay the melody on a single treble staff, fill gaps with rests, tie across
    barlines
  * place chord symbols (``<harmony>``) above the staff at their quantised onsets
  * stamp key / time-signature / tempo metadata

music21 is imported lazily so the package stays importable in a minimal env.
"""
from __future__ import annotations

import math
from bisect import bisect_right
from dataclasses import dataclass, field
from pathlib import Path
from statistics import median

from app.config import Settings, get_settings
from app.core.exceptions import ScoreValidationError
from app.core.logging import get_logger
from app.services.audio_analyzer import AnalysisResult

logger = get_logger(__name__)

# our theory quality tag -> music21 ChordSymbol "kind"
_CHORD_KIND = {
    "maj": "major",
    "min": "minor",
    "dim": "diminished",
    "aug": "augmented",
    "dom7": "dominant-seventh",
    "maj7": "major-seventh",
    "min7": "minor-seventh",
    "min7b5": "half-diminished",
    "sus4": "suspended-fourth",
    "sus2": "suspended-second",
}
_PC_TO_NAME = ["C", "C#", "D", "E-", "E", "F", "F#", "G", "A-", "A", "B-", "B"]


@dataclass
class BuildResult:
    musicxml_path: str
    measure_count: int
    note_count: int
    rest_count: int
    chord_symbol_count: int
    dropped_notes: int
    warnings: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# quantisation grid
# --------------------------------------------------------------------------- #
class QuantGrid:
    """Maps absolute seconds to a quarterLength offset snapped to a beat grid."""

    def __init__(self, beat_times: list[float], *, beat_unit: int, division: int):
        if len(beat_times) < 2:
            raise ScoreValidationError(
                "Cannot build a score: need at least 2 beat times from analysis"
            )
        self.beats = sorted(float(t) for t in beat_times)
        diffs = [b - a for a, b in zip(self.beats, self.beats[1:], strict=False)]
        self.period = median(diffs) if diffs else 0.5
        self.ql_per_beat = 4.0 / beat_unit
        # subdivisions per beat (>=1); 4/4 + division 16 -> 4 (sixteenths)
        self.subdiv = max(1, round(division * self.ql_per_beat / 4.0))
        self.min_ql = self.ql_per_beat / self.subdiv

    def _beat_position(self, t: float) -> float:
        beats = self.beats
        if t <= beats[0]:
            return (t - beats[0]) / self.period
        if t >= beats[-1]:
            return (len(beats) - 1) + (t - beats[-1]) / self.period
        i = bisect_right(beats, t) - 1
        span = beats[i + 1] - beats[i] or self.period
        return i + (t - beats[i]) / span

    def sec_to_ql(self, t: float) -> float:
        steps = round(self._beat_position(t) * self.subdiv)
        return steps * self.min_ql

    def snap_duration(self, start_ql: float, end_ql: float) -> float:
        return max(self.min_ql, round((end_ql - start_ql) / self.min_ql) * self.min_ql)


# --------------------------------------------------------------------------- #
def build_musicxml(
    analysis: AnalysisResult,
    out_path: str | Path,
    *,
    settings: Settings | None = None,
    title: str | None = None,
    quantize_division: int | None = None,
) -> BuildResult:
    settings = settings or get_settings()
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    division = quantize_division or settings.quantize_division

    from music21 import (  # noqa: PLC0415
        clef,
        harmony,
        key,
        metadata,
        meter,
        note,
        stream,
        tempo,
    )

    warnings: list[str] = []
    ts_str = analysis.time_signature or settings.default_time_signature
    try:
        numerator, denominator = (int(x) for x in ts_str.split("/"))
    except ValueError:
        numerator, denominator = 4, 4
        warnings.append(f"Unparseable time signature {ts_str!r}; defaulting to 4/4")

    grid = QuantGrid(
        analysis.beat_times,
        beat_unit=denominator,
        division=division,
    )
    # Barlines are anchored to the first analysed beat and drawn every
    # ``numerator`` beats. We trust beat tracking more than the fallback
    # downbeat phase estimate, so a disagreement is surfaced as a warning
    # rather than shifting every bar.
    origin = analysis.beat_times[0]
    if analysis.downbeat_times:
        drift = abs(analysis.downbeat_times[0] - origin)
        if grid.period and drift > grid.period * 0.5:
            warnings.append(
                f"Analysed downbeat is {drift:.2f}s from the first beat; "
                "barlines anchored to the beat grid (possible anacrusis ignored)"
            )

    part = stream.Part(id="lead")
    part.insert(0.0, clef.TrebleClef())
    part.insert(0.0, _make_key(key, analysis.key, warnings))
    part.insert(0.0, meter.TimeSignature(f"{numerator}/{denominator}"))
    if analysis.bpm and analysis.bpm > 0:
        part.insert(0.0, tempo.MetronomeMark(number=round(analysis.bpm)))

    dropped, note_count = _insert_melody(part, note, analysis, grid, origin, warnings)
    _pad_to_full_bars(part, note, analysis, grid, origin, numerator, denominator)

    # notation pass: measures + rests + ties across barlines
    try:
        part.makeRests(fillGaps=True, inPlace=True, hideRests=False)
        part.makeNotation(inPlace=True)
    except Exception as exc:  # music21 raises assorted errors on odd input
        raise ScoreValidationError(f"music21 failed to lay out the score: {exc}") from exc

    chord_count = _attach_chord_symbols(part, harmony, analysis, grid, origin, warnings)

    score = stream.Score()
    score.metadata = metadata.Metadata()
    score.metadata.title = title or "AutoScore Lead Sheet"
    score.metadata.composer = f"AutoScore ({', '.join(analysis.backends.values()) or 'analysis'})"
    score.insert(0.0, part)

    measures = list(part.getElementsByClass(stream.Measure))
    rest_count = sum(len(m.getElementsByClass(note.Rest)) for m in measures)
    if not measures:
        raise ScoreValidationError("Score has no measures after notation")

    try:
        score.write("musicxml", fp=str(out_path))
    except Exception as exc:
        raise ScoreValidationError(f"Failed to write MusicXML: {exc}") from exc

    result = BuildResult(
        musicxml_path=str(out_path),
        measure_count=len(measures),
        note_count=note_count,
        rest_count=rest_count,
        chord_symbol_count=chord_count,
        dropped_notes=dropped,
        warnings=warnings,
    )
    logger.info(
        "musicxml built: %s measures=%d notes=%d chords=%d dropped=%d",
        out_path.name, result.measure_count, note_count, chord_count, dropped,
    )
    return result


# --------------------------------------------------------------------------- #
def _make_key(key_mod, key_name: str, warnings: list[str]):
    parts = (key_name or "C major").split()
    tonic = parts[0].replace("b", "-") if parts else "C"
    mode = parts[1].lower() if len(parts) > 1 else "major"
    try:
        return key_mod.Key(tonic, mode)
    except Exception:  # noqa: BLE001
        warnings.append(f"Unparseable key {key_name!r}; defaulting to C major")
        return key_mod.Key("C", "major")


def _pad_to_full_bars(part, note_mod, analysis, grid: QuantGrid, origin, numerator, denominator):
    """Ensure the part spans a whole number of bars (and is non-empty)."""
    origin_ql = grid.sec_to_ql(origin)
    bar_ql = numerator * (4.0 / denominator)

    ends = [grid.sec_to_ql(analysis.beat_times[-1]) - origin_ql, float(part.highestTime)]
    ends += [
        grid.sec_to_ql(c.end_sec) - origin_ql
        for c in analysis.chords
        if c.symbol and c.symbol.upper() not in {"N.C.", "NC"}
    ]
    total_ql = max(ends)
    bars = max(1, math.ceil(total_ql / bar_ql - 1e-6))
    total_ql = bars * bar_ql

    if part.highestTime < total_ql - 1e-6:
        part.insert(part.highestTime, note_mod.Rest(quarterLength=total_ql - part.highestTime))


def _insert_melody(part, note_mod, analysis, grid: QuantGrid, origin: float, warnings):
    events: list[tuple[float, float, int]] = []
    dropped = 0
    for n in sorted(analysis.notes, key=lambda x: x.start_sec):
        start_ql = grid.sec_to_ql(n.start_sec) - grid.sec_to_ql(origin)
        end_ql = grid.sec_to_ql(n.end_sec) - grid.sec_to_ql(origin)
        if end_ql <= 0:
            dropped += 1  # entirely before the first barline
            continue
        start_ql = max(0.0, start_ql)
        midi = min(127, max(0, int(n.midi)))
        events.append((start_ql, grid.snap_duration(start_ql, end_ql), midi))

    if dropped:
        warnings.append(f"{dropped} melody note(s) before the first downbeat were dropped")

    # enforce monophony: truncate a note that overruns the next onset
    cleaned: list[tuple[float, float, int]] = []
    for i, (start, dur, midi) in enumerate(events):
        end = start + dur
        if i + 1 < len(events):
            nxt = events[i + 1][0]
            if nxt < end:
                dur = nxt - start
        if dur < grid.min_ql:
            continue
        if cleaned and start < cleaned[-1][0] + cleaned[-1][1] - 1e-6:
            continue  # fully overlapped duplicate
        cleaned.append((start, dur, midi))

    note_count = 0
    for start, dur, midi in cleaned:
        m21n = note_mod.Note(midi=midi)
        m21n.quarterLength = dur
        part.insert(start, m21n)
        note_count += 1

    if note_count == 0:
        warnings.append("No melody notes survived quantisation; score is rests only")
    return dropped, note_count


def _attach_chord_symbols(part, harmony_mod, analysis, grid: QuantGrid, origin: float, warnings):
    from music21 import stream as _stream  # noqa: PLC0415

    measures = list(part.getElementsByClass(_stream.Measure))
    if not measures:
        return 0
    bounds = []
    for m in measures:
        length = m.barDuration.quarterLength or m.quarterLength or 4.0
        bounds.append((m.offset, m.offset + length, m))

    origin_ql = grid.sec_to_ql(origin)
    count = 0
    last_symbol = None
    for c in sorted(analysis.chords, key=lambda x: x.start_sec):
        if not c.symbol or c.symbol.upper() in {"N.C.", "NC"}:
            last_symbol = None
            continue
        cs = _make_chord_symbol(harmony_mod, c, warnings)
        if cs is None:
            continue
        if cs.figure == last_symbol:
            continue  # collapse immediate repeats
        raw_offset = max(0.0, grid.sec_to_ql(c.start_sec) - origin_ql)
        # chord changes sit on beats in a lead sheet
        offset = round(raw_offset / grid.ql_per_beat) * grid.ql_per_beat
        target = next((b for b in bounds if b[0] <= offset < b[1]), None)
        if target is None:
            if offset >= bounds[-1][1]:
                continue  # past the end of the piece
            target = bounds[0]
        _, m_start, measure = target[0], target[0], target[2]
        cs.writeAsChord = False
        cs.quarterLength = 0.0
        measure.insert(offset - m_start, cs)
        last_symbol = cs.figure
        count += 1

    if count == 0 and analysis.chords:
        warnings.append("No chord symbols could be placed")
    return count


def _make_chord_symbol(harmony_mod, chord_event, warnings):
    try:
        if chord_event.root_pc is not None and chord_event.quality in _CHORD_KIND:
            root_name = _PC_TO_NAME[chord_event.root_pc % 12]
            return harmony_mod.ChordSymbol(
                root=root_name, kind=_CHORD_KIND[chord_event.quality]
            )
        return harmony_mod.ChordSymbol(chord_event.symbol)
    except Exception:  # noqa: BLE001
        warnings.append(f"Could not parse chord symbol {chord_event.symbol!r}")
        return None
