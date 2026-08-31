from __future__ import annotations

import pytest

from app.core.exceptions import ScoreValidationError
from app.services.audio_analyzer.types import AnalysisResult, ChordEvent, NoteEvent
from app.services.xml_builder import QuantGrid, build_musicxml

pytest.importorskip("music21")
pytest.importorskip("librosa")
from tests.synth import render_stems  # noqa: E402


# --------------------------------------------------------------------------- #
# QuantGrid unit tests
# --------------------------------------------------------------------------- #
def test_quantgrid_snaps_onsets_to_sixteenth_grid():
    beats = [0.0, 0.5, 1.0, 1.5, 2.0]  # 120 BPM
    grid = QuantGrid(beats, beat_unit=4, division=16)
    assert grid.subdiv == 4
    assert grid.min_ql == pytest.approx(0.25)
    assert grid.sec_to_ql(0.0) == pytest.approx(0.0)
    assert grid.sec_to_ql(0.5) == pytest.approx(1.0)   # one quarter in
    assert grid.sec_to_ql(0.62) == pytest.approx(1.25)  # snaps to nearest 16th
    assert grid.sec_to_ql(1.0) == pytest.approx(2.0)


def test_quantgrid_extrapolates_past_last_beat():
    grid = QuantGrid([0.0, 0.5, 1.0], beat_unit=4, division=16)
    assert grid.sec_to_ql(2.0) == pytest.approx(4.0, abs=0.25)


def test_quantgrid_rejects_too_few_beats():
    with pytest.raises(ScoreValidationError):
        QuantGrid([0.0], beat_unit=4, division=16)


# --------------------------------------------------------------------------- #
# build_musicxml
# --------------------------------------------------------------------------- #
def _synthetic_analysis() -> AnalysisResult:
    beats = [i * 0.5 for i in range(17)]  # 8 bars of 4/4 at 120 BPM
    notes = [
        NoteEvent(start_sec=i * 0.5, end_sec=i * 0.5 + 0.45, midi=60 + (i % 8))
        for i in range(16)
    ]
    chords = [
        ChordEvent(start_sec=b * 2.0, end_sec=b * 2.0 + 2.0, symbol=sym, root_pc=pc, quality=q)
        for b, (sym, pc, q) in enumerate(
            [("C", 0, "maj"), ("Am", 9, "min"), ("F", 5, "maj"), ("G", 7, "dom7")]
        )
    ]
    return AnalysisResult(
        duration_sec=8.0, bpm=120.0, beat_times=beats, downbeat_times=beats[::4],
        key="C major", time_signature="4/4", notes=notes, chords=chords,
        backends={"melody": "test"},
    )


def test_build_produces_reparseable_lead_sheet(tmp_path):
    from music21 import converter

    out = tmp_path / "full.musicxml"
    res = build_musicxml(_synthetic_analysis(), out, title="Unit")
    assert out.is_file()
    assert res.measure_count == 4
    assert res.note_count == 16
    assert res.chord_symbol_count == 4
    assert res.dropped_notes == 0

    score = converter.parse(str(out))
    part = score.parts[0]
    assert part.recurse().getElementsByClass("TimeSignature")[0].ratioString == "4/4"
    figures = [cs.figure for cs in part.recurse().getElementsByClass("ChordSymbol")]
    assert figures[0] == "C"
    assert "G7" in figures


def test_build_with_no_notes_is_rest_only(tmp_path):
    analysis = _synthetic_analysis()
    analysis.notes = []
    res = build_musicxml(analysis, tmp_path / "empty.musicxml")
    assert res.note_count == 0
    assert res.rest_count > 0
    assert any("rests only" in w for w in res.warnings)


def test_build_skips_nc_chords(tmp_path):
    analysis = _synthetic_analysis()
    analysis.chords.append(
        ChordEvent(start_sec=4.0, end_sec=6.0, symbol="N.C.", root_pc=None, quality=None)
    )
    res = build_musicxml(analysis, tmp_path / "nc.musicxml")
    assert res.chord_symbol_count == 4  # N.C. not emitted


def test_build_raises_on_insufficient_beats(tmp_path):
    analysis = _synthetic_analysis()
    analysis.beat_times = [0.0]
    with pytest.raises(ScoreValidationError):
        build_musicxml(analysis, tmp_path / "bad.musicxml")


def test_build_from_real_analysis_pipeline(tmp_path):
    from music21 import converter

    from app.services.audio_analyzer import analyze

    stems = render_stems(tmp_path / "stems")
    analysis = analyze(stems)
    res = build_musicxml(analysis, tmp_path / "pipeline.musicxml")

    assert res.measure_count >= 6
    score = converter.parse(str(res.musicxml_path))
    detected = {
        cs.figure[0] for cs in score.recurse().getElementsByClass("ChordSymbol")
    }
    assert {"C", "F", "G"} & detected


def test_build_route_reads_stored_analysis(tmp_settings, tmp_path):
    from fastapi.testclient import TestClient

    from app.config import get_settings
    from app.main import create_app

    job_id = "buildjob"
    stem_dir = tmp_settings.stems_path / job_id
    stems = render_stems(stem_dir)
    for name, path in stems.items():
        (stem_dir / f"{name}.wav").write_bytes(path.read_bytes())

    app = create_app()
    app.dependency_overrides[get_settings] = lambda: tmp_settings
    client = TestClient(app)

    assert client.post(f"/api/analyze/{job_id}", json={}).status_code == 200
    resp = client.post(f"/api/build/{job_id}", json={"title": "Route Test"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["measure_count"] >= 6
    assert (tmp_settings.outputs_path / job_id / "full.musicxml").is_file()

    missing = client.post("/api/build/no-analysis", json={})
    assert missing.status_code == 422
