from __future__ import annotations

import pytest

from app.core.exceptions import AudioAnalysisError
from app.services.audio_analyzer import analyze, backend_status, theory

librosa = pytest.importorskip("librosa")
from tests.synth import render_stems  # noqa: E402


@pytest.fixture(scope="module")
def stems(tmp_path_factory):
    return render_stems(tmp_path_factory.mktemp("stems"))


@pytest.fixture(scope="module")
def result(stems):
    return analyze(stems)


def test_backend_status_reports_fallback_chain():
    sel = backend_status()["selected"]
    assert sel["melody"] in {"basic_pitch", "librosa_pyin"}
    assert sel["rhythm"] in {"madmom", "librosa_beat"}
    assert sel["harmony"] in {"essentia", "chroma_template"}


def test_tempo_is_close_to_120(result):
    # beat trackers may land on a metrical multiple; accept 60/120/240.
    assert min(abs(result.bpm - b) for b in (60, 120, 240)) < 12


def test_meter_and_grid(result):
    # librosa fallback trusts the configured 4/4; downbeat phase is searched.
    assert result.time_signature == "4/4"
    assert len(result.beat_times) > 20
    assert result.downbeat_times == sorted(result.downbeat_times)
    assert result.downbeat_times[0] < result.beat_times[4] + 1e-6
    # downbeats should be a 4-beat subgrid
    if len(result.downbeat_times) >= 2:
        span = result.downbeat_times[1] - result.downbeat_times[0]
        beat = 60.0 / result.bpm
        assert span == pytest.approx(4 * beat, rel=0.35)


def test_key_is_c_major(result):
    assert result.key == "C major"


def test_chords_track_the_progression(result):
    assert result.chords, "expected at least one chord span"
    # C, F and G are the diatonic pillars of the synthetic C-Am-F-G progression.
    detected_roots = {
        theory.pc_name(c.root_pc) for c in result.chords if c.root_pc is not None
    }
    assert {"C", "F", "G"} & detected_roots
    assert sum(c.duration_sec for c in result.chords) > 8


def test_melody_notes_match_synthetic_line(result):
    assert len(result.notes) >= 8
    midis = [n.midi for n in result.notes]
    expected = {72, 74, 76, 77}
    hits = sum(1 for m in midis if m in expected)
    assert hits / len(midis) > 0.5
    for n in result.notes:
        assert n.end_sec > n.start_sec


def test_backends_recorded(result):
    assert set(result.backends) >= {"rhythm", "harmony", "melody", "harmonic_source"}


def test_missing_vocal_raises(stems):
    with pytest.raises(AudioAnalysisError):
        analyze({"bass": stems["bass"], "drums": stems["drums"]})


def test_window_slice_reanchors_to_absolute_time(stems):
    full = analyze(stems)
    windowed = analyze(stems, window=(4.0, 8.0))
    assert windowed.window_offset_sec == pytest.approx(4.0, abs=0.05)
    assert windowed.beat_times[0] >= 3.5
    assert windowed.duration_sec < full.duration_sec


def test_analyze_route_end_to_end(tmp_settings, stems):
    from fastapi.testclient import TestClient

    from app.config import get_settings
    from app.main import create_app

    job_id = "synthjob"
    stem_dir = tmp_settings.stems_path / job_id
    stem_dir.mkdir(parents=True, exist_ok=True)
    for name, path in stems.items():
        (stem_dir / f"{name}.wav").write_bytes(path.read_bytes())

    app = create_app()
    app.dependency_overrides[get_settings] = lambda: tmp_settings
    client = TestClient(app)

    resp = client.post(f"/api/analyze/{job_id}", json={})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["key"] == "C major"
    assert body["time_signature"] == "4/4"
    assert len(body["notes"]) >= 8
    assert (tmp_settings.outputs_path / job_id / "analysis.json").is_file()

    missing = client.post("/api/analyze/nope", json={})
    assert missing.status_code == 502
    assert missing.json()["error"]["code"] == "audio_analysis_failed"
