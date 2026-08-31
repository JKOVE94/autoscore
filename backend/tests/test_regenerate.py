from __future__ import annotations

import pytest

from app.core.exceptions import AudioAnalysisError
from app.services.audio_analyzer import (
    analyze,
    analyze_window,
    measure_windows,
    merge_window,
    selected_span,
)

pytest.importorskip("librosa")
pytest.importorskip("music21")
from tests.synth import render_stems  # noqa: E402


@pytest.fixture(scope="module")
def stems(tmp_path_factory):
    return render_stems(tmp_path_factory.mktemp("regen"))


@pytest.fixture(scope="module")
def analysis(stems):
    return analyze(stems)


def test_measure_windows_are_contiguous(analysis):
    windows = measure_windows(analysis)
    assert len(windows) >= 6
    for (_, end), (start, _) in zip(windows, windows[1:], strict=False):
        assert end == pytest.approx(start, abs=0.05)


def test_selected_span_validates_measure_numbers(analysis):
    t0, t1, valid = selected_span(analysis, [3, 4, 999])
    assert valid == [3, 4]
    assert t1 > t0
    with pytest.raises(AudioAnalysisError):
        selected_span(analysis, [999])


def test_analyze_window_returns_events_within_span(stems, analysis):
    t0, t1, _ = selected_span(analysis, [3, 4])
    notes, chords = analyze_window(stems, analysis, (t0, t1))
    assert notes and chords
    assert all(t0 - 0.2 <= n.start_sec < t1 for n in notes)
    mids = [n.midi for n in notes]
    assert sum(1 for m in mids if m in {72, 74, 76, 77}) / len(mids) > 0.5


def test_merge_window_only_replaces_in_span(stems, analysis):
    t0, t1, _ = selected_span(analysis, [4])
    notes, chords = analyze_window(stems, analysis, (t0, t1))
    merged = merge_window(analysis, notes, chords, (t0, t1))

    outside_before = [n for n in analysis.notes if n.end_sec <= t0 or n.start_sec >= t1]
    outside_after = [n for n in merged.notes if n.end_sec <= t0 or n.start_sec >= t1]
    assert len(outside_after) == len(outside_before)
    assert merged.backends["regen"] == "window"
    assert merged.beat_times == analysis.beat_times  # grid untouched


def test_regenerate_route_end_to_end(tmp_settings, stems):
    from fastapi.testclient import TestClient

    from app.config import get_settings
    from app.main import create_app

    job_id = "regenjob"
    stem_dir = tmp_settings.stems_path / job_id
    rendered = render_stems(stem_dir)
    for name, path in rendered.items():
        (stem_dir / f"{name}.wav").write_bytes(path.read_bytes())

    app = create_app()
    app.dependency_overrides[get_settings] = lambda: tmp_settings
    client = TestClient(app)

    assert client.post(f"/api/analyze/{job_id}", json={}).status_code == 200
    assert client.post(f"/api/build/{job_id}", json={}).status_code == 200

    measures = client.get(f"/api/measures/{job_id}").json()
    assert len(measures) >= 6
    assert measures[0]["number"] == 1

    resp = client.post(
        f"/api/regenerate-measure/{job_id}",
        json={"measures": [2, 3], "pitch_sensitivity": 0.7, "quantize_division": 16},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["changed_measures"] == [2, 3]
    assert body["span_sec"][0] < body["span_sec"][1]
    assert "<score-partwise" in body["musicxml"]
    assert body["measure_count"] >= 6

    bad = client.post(f"/api/regenerate-measure/{job_id}", json={"measures": [9999]})
    assert bad.status_code == 502

    empty = client.post(f"/api/regenerate-measure/{job_id}", json={"measures": []})
    assert empty.status_code == 422  # pydantic min_length


def test_regenerate_without_analysis_errors(tmp_settings):
    from fastapi.testclient import TestClient

    from app.config import get_settings
    from app.main import create_app

    app = create_app()
    app.dependency_overrides[get_settings] = lambda: tmp_settings
    client = TestClient(app)
    resp = client.post("/api/regenerate-measure/ghost", json={"measures": [1]})
    assert resp.status_code == 422
