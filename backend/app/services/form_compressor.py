"""Step 5: lead-sheet form compression.

Collapses repeated sections of a rendered score into repeat barlines and
1st/2nd endings (via music21's ``RepeatFinder``), then applies a conservative
D.S. al Coda / al Fine for one clean non-adjacent tail repeat. Also derives a
compact song-form string (A A B A ...) from the analysed measures.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.config import Settings, get_settings
from app.core.exceptions import ScoreValidationError
from app.core.logging import get_logger
from app.services.audio_analyzer import AnalysisResult
from app.services.audio_analyzer.regen import measure_windows

logger = get_logger(__name__)


@dataclass
class CompressionReport:
    original_measures: int
    compressed_measures: int
    operations: list[str] = field(default_factory=list)
    song_form: str | None = None
    similar_groups: list[tuple[list[int], list[int]]] = field(default_factory=list)


# --------------------------------------------------------------------------- #
def compress_musicxml(
    src_path: str | Path,
    out_path: str | Path,
    *,
    analysis: AnalysisResult | None = None,
    settings: Settings | None = None,
) -> CompressionReport:
    settings = settings or get_settings()
    src_path, out_path = Path(src_path), Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    from music21 import bar, converter, repeat, stream  # noqa: PLC0415

    try:
        score = converter.parse(str(src_path))
    except Exception as exc:  # noqa: BLE001
        raise ScoreValidationError(f"Could not parse score: {exc}") from exc

    part = score.parts[0] if getattr(score, "parts", None) else score
    measures_before = len(part.getElementsByClass(stream.Measure))
    if measures_before < 2:
        raise ScoreValidationError("Score has too few measures to compress")

    operations: list[str] = []

    # --- 1. repeat barlines + 1st/2nd endings --------------------------------
    rf = repeat.RepeatFinder(part)
    try:
        raw_groups = rf.getSimilarMeasureGroups()
    except Exception:  # noqa: BLE001
        raw_groups = []
    similar_groups = [(list(a), list(b)) for a, b in raw_groups]

    try:
        simplified = rf.simplify()
    except Exception as exc:  # noqa: BLE001 - RepeatFinder is picky
        logger.warning("RepeatFinder.simplify failed (%s); keeping score as-is", exc)
        simplified = part

    working = _as_part(simplified, stream)
    n_after_repeat = len(working.getElementsByClass(stream.Measure))
    if n_after_repeat < measures_before:
        operations.append(
            f"repeat/volta: {measures_before} → {n_after_repeat} measures"
        )
        n_brackets = len(list(working.getElementsByClass("RepeatBracket")))
        if n_brackets:
            operations.append(f"{n_brackets} volta bracket(s) inserted")

    # --- 2. conservative D.S. al Coda / al Fine -----------------------------
    working, ds_ops = _apply_dal_segno(working, stream, repeat, bar)
    operations.extend(ds_ops)

    final_count = len(working.getElementsByClass(stream.Measure))

    # --- 3. song form -----------------------------------------------------
    song_form = _song_form(analysis) if analysis else None

    out_score = stream.Score()
    _copy_metadata(score, out_score, song_form)
    out_score.insert(0.0, working)
    try:
        out_score.write("musicxml", fp=str(out_path))
    except Exception as exc:  # noqa: BLE001
        raise ScoreValidationError(f"Failed to write compressed MusicXML: {exc}") from exc

    if not operations:
        operations.append("no repeated sections detected; score copied unchanged")

    logger.info(
        "form compress: %d → %d measures, ops=%s", measures_before, final_count, operations
    )
    return CompressionReport(
        original_measures=measures_before,
        compressed_measures=final_count,
        operations=operations,
        song_form=song_form,
        similar_groups=similar_groups,
    )


# --------------------------------------------------------------------------- #
def _as_part(obj, stream_mod):
    if isinstance(obj, stream_mod.Part):
        return obj
    part = stream_mod.Part()
    for el in obj.getElementsByClass(stream_mod.Measure):
        part.append(el)
    # carry spanners (RepeatBrackets) across
    for sp in obj.getElementsByClass("RepeatBracket"):
        part.insert(0, sp)
    return part


def _copy_metadata(src, dst, song_form):
    from music21 import metadata  # noqa: PLC0415

    dst.metadata = metadata.Metadata()
    title = "AutoScore Lead Sheet"
    if src.metadata and src.metadata.title:
        title = src.metadata.title
    dst.metadata.title = title
    if song_form:
        dst.metadata.add("description", f"Form: {song_form}")


# --------------------------------------------------------------------------- #
def _apply_dal_segno(part, stream_mod, repeat_mod, bar_mod):
    """One clean non-adjacent tail repeat -> Segno + D.S. al Coda / al Fine."""
    measures = list(part.getElementsByClass(stream_mod.Measure))
    n = len(measures)
    if n < 6:
        return part, []

    try:
        groups = repeat_mod.RepeatFinder(part).getSimilarMeasureGroups()
    except Exception:  # noqa: BLE001
        return part, []

    best: tuple[list[int], list[int]] | None = None
    for first, second in groups:
        if len(first) != len(second) or len(first) < 3:
            continue
        if second[0] <= first[-1] + 1:  # adjacent -> RepeatFinder already handled
            continue
        if best is None or len(first) > len(best[0]):
            best = (list(first), list(second))
    if best is None:
        return part, []

    first, second = best
    # measure numbers are 1-based positions in `measures`
    a0, a1 = first[0] - 1, first[-1] - 1
    b0, b1 = second[0] - 1, second[-1] - 1
    if not (0 <= a0 <= a1 < b0 <= b1 < n):
        return part, []

    coda_tail = measures[b1 + 1 :]
    ops: list[str] = []

    measures[a0].insert(0.0, repeat_mod.Segno())

    if coda_tail:
        # To Coda at end of the first section, Coda before the tail
        _insert_at_end(measures[a1], repeat_mod.Coda())
        _insert_at_end(measures[b0 - 1], repeat_mod.DalSegnoAlCoda())
        coda_tail[0].insert(0.0, repeat_mod.Coda())
        ops.append(
            f"D.S. al Coda: measures {second[0]}–{second[-1]} replaced "
            f"(segno @ m{first[0]}, coda tail m{b1 + 2}–{n})"
        )
    else:
        _insert_at_end(measures[a1], repeat_mod.Fine())
        _insert_at_end(measures[b0 - 1], repeat_mod.DalSegnoAlFine())
        ops.append(
            f"D.S. al Fine: measures {second[0]}–{second[-1]} replaced (segno @ m{first[0]})"
        )

    kept = measures[:b0] + measures[b1 + 1 :]
    new_part = stream_mod.Part(id=getattr(part, "id", "lead"))
    for i, m in enumerate(kept, start=1):
        m.number = i
        new_part.append(m)
    for sp in part.getElementsByClass("RepeatBracket"):
        if all(m in kept for m in sp.getSpannedElements()):
            new_part.insert(0, sp)
    return new_part, ops


def _insert_at_end(measure, element) -> None:
    offset = measure.barDuration.quarterLength or measure.highestTime or 0.0
    measure.insert(offset, element)


# --------------------------------------------------------------------------- #
def _song_form(analysis: AnalysisResult) -> str | None:
    windows = measure_windows(analysis)
    if len(windows) < 2:
        return None

    def chord_seq(t0, t1):
        return tuple(
            c.symbol for c in analysis.chords
            if t0 <= (c.start_sec + c.end_sec) / 2 < t1 and c.symbol
        )

    def pitch_set(t0, t1):
        return tuple(sorted({n.midi % 12 for n in analysis.notes if t0 <= n.start_sec < t1}))

    fps = [(chord_seq(t0, t1), pitch_set(t0, t1)) for t0, t1 in windows]

    labels: list[str] = []
    seen: dict[tuple, str] = {}
    next_label = ord("A")
    for fp in fps:
        if fp not in seen:
            seen[fp] = chr(next_label)
            next_label += 1
        labels.append(seen[fp])

    # collapse consecutive equal labels into runs
    runs: list[tuple[str, int]] = []
    for lb in labels:
        if runs and runs[-1][0] == lb:
            runs[-1] = (lb, runs[-1][1] + 1)
        else:
            runs.append((lb, 1))
    return " ".join(f"{lb}×{cnt}" if cnt > 1 else lb for lb, cnt in runs)
