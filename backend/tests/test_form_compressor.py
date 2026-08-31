from __future__ import annotations

import pytest

pytest.importorskip("music21")

from app.services.form_compressor import (  # noqa: E402
    _apply_dal_segno,
    _song_form,
    compress_musicxml,
)


def _build_score(measures: list[tuple[str, str]], path):
    """measures = [(chord_figure, 'CDEF'), ...] -> writes a MusicXML file."""
    from music21 import harmony, meter, note, stream

    score = stream.Score()
    part = stream.Part(id="lead")
    part.append(meter.TimeSignature("4/4"))
    for i, (fig, pitches) in enumerate(measures):
        m = stream.Measure(number=i + 1)
        if fig:
            m.insert(0.0, harmony.ChordSymbol(fig))
        for p in pitches:
            m.append(note.Note(p, quarterLength=1.0))
        part.append(m)
    score.insert(0, part)
    score.write("musicxml", fp=str(path))
    return path


SEQ = [("C", "CDEF"), ("G", "GBDG"), ("F", "FACF"), ("a", "ACEA")]


def test_simple_adjacent_repeat_is_collapsed(tmp_path):
    from music21 import converter

    src = _build_score([SEQ[i % 4] for i in range(8)], tmp_path / "s.xml")
    report = compress_musicxml(src, tmp_path / "c.xml")

    assert report.original_measures == 8
    assert report.compressed_measures == 4
    assert any("repeat" in op for op in report.operations)

    score = converter.parse(str(tmp_path / "c.xml"))
    barlines = [
        type(m.rightBarline).__name__
        for m in score.parts[0].getElementsByClass("Measure")
        if m.rightBarline
    ]
    assert "Repeat" in barlines


def test_first_second_endings_become_volta(tmp_path):
    from music21 import converter

    measures = [SEQ[0], SEQ[1], SEQ[2], ("G", "GGGG"),
                SEQ[0], SEQ[1], SEQ[2], ("C", "CCCC")]
    src = _build_score(measures, tmp_path / "s.xml")
    report = compress_musicxml(src, tmp_path / "c.xml")

    assert report.compressed_measures < report.original_measures
    score = converter.parse(str(tmp_path / "c.xml"))
    brackets = list(score.parts[0].recurse().getElementsByClass("RepeatBracket"))
    assert len(brackets) == 2


def test_dal_segno_al_coda_for_non_adjacent_repeat(tmp_path):
    from music21 import bar, harmony, meter, note, repeat, stream

    part = stream.Part(id="lead")
    part.append(meter.TimeSignature("4/4"))
    a = [("C", "CDEF"), ("G", "GBDG"), ("a", "ACEA")]
    layout = a + [("F", "FACF"), ("d", "DFAD")] + a + [("G", "GBDG"), ("C", "CEGC")]
    for i, (fig, pitches) in enumerate(layout):
        m = stream.Measure(number=i + 1)
        m.insert(0.0, harmony.ChordSymbol(fig))
        for p in pitches:
            m.append(note.Note(p, quarterLength=1.0))
        part.append(m)

    new_part, ops = _apply_dal_segno(part, stream, repeat, bar)
    assert ops and "D.S." in ops[0]

    kinds = {
        type(e).__name__
        for m in new_part.getElementsByClass(stream.Measure)
        for e in m
    }
    assert "Segno" in kinds
    assert "DalSegnoAlCoda" in kinds
    assert len(list(new_part.getElementsByClass(stream.Measure))) < len(layout)


def test_song_form_string_marks_repeats():
    from app.services.audio_analyzer.types import AnalysisResult, ChordEvent

    beats = [i * 0.5 for i in range(17)]  # 4 bars of 4/4
    chords = [
        ChordEvent(start_sec=b * 2.0, end_sec=b * 2.0 + 2.0, symbol=sym)
        for b, sym in enumerate(["C", "G", "C", "G"])
    ]
    analysis = AnalysisResult(
        duration_sec=8.0, bpm=120.0, beat_times=beats, downbeat_times=beats[::4],
        key="C major", time_signature="4/4", notes=[], chords=chords,
    )
    form = _song_form(analysis)
    assert form is not None
    # bars 1&3 (C) share a label, 2&4 (G) share a label
    labels = form.replace("×", " ").split()
    assert labels[0] == labels[2]


def test_compress_route_end_to_end(tmp_settings):
    import pytest as _pytest

    _pytest.importorskip("librosa")
    from fastapi.testclient import TestClient

    from app.config import get_settings
    from app.main import create_app
    from tests.synth import render_stems

    job_id = "compressjob"
    stem_dir = tmp_settings.stems_path / job_id
    for name, path in render_stems(stem_dir).items():
        (stem_dir / f"{name}.wav").write_bytes(path.read_bytes())

    app = create_app()
    app.dependency_overrides[get_settings] = lambda: tmp_settings
    client = TestClient(app)

    assert client.post(f"/api/analyze/{job_id}", json={}).status_code == 200
    assert client.post(f"/api/build/{job_id}", json={}).status_code == 200

    resp = client.post(f"/api/compress/{job_id}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["compressed_measures"] <= body["original_measures"]
    assert "<score-partwise" in body["musicxml"]
    assert body["song_form"]

    ls = client.get(f"/api/lead-sheet/{job_id}")
    assert ls.status_code == 200
    assert ls.headers["content-type"].startswith("application/vnd.recordare.musicxml")


def test_compress_without_build_errors(tmp_settings):
    from fastapi.testclient import TestClient

    from app.config import get_settings
    from app.main import create_app

    app = create_app()
    app.dependency_overrides[get_settings] = lambda: tmp_settings
    client = TestClient(app)
    assert client.post("/api/compress/ghost").status_code == 422
    assert client.get("/api/lead-sheet/ghost").status_code == 404
