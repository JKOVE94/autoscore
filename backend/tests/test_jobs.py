from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import create_app

pytest.importorskip("librosa")
from tests.synth import render_stems  # noqa: E402


@pytest.fixture
def client(tmp_settings):
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: tmp_settings
    return TestClient(app)


def test_job_status_transitions(client, tmp_settings, tmp_path):
    job_id = "j1"
    assert client.get(f"/api/jobs/{job_id}").json() == {
        "job_id": job_id,
        "has_upload": False,
        "has_stems": False,
        "has_analysis": False,
        "has_musicxml": False,
    }

    stem_dir = tmp_settings.stems_path / job_id
    stems = render_stems(stem_dir)
    for name, path in stems.items():
        (stem_dir / f"{name}.wav").write_bytes(path.read_bytes())

    assert client.post(f"/api/analyze/{job_id}", json={}).status_code == 200
    assert client.post(f"/api/build/{job_id}", json={}).status_code == 200

    status = client.get(f"/api/jobs/{job_id}").json()
    assert status["has_stems"] and status["has_analysis"] and status["has_musicxml"]

    score = client.get(f"/api/score/{job_id}")
    assert score.status_code == 200
    assert score.headers["content-type"].startswith("application/vnd.recordare.musicxml")
    assert b"score-partwise" in score.content

    analysis = client.get(f"/api/analysis/{job_id}").json()
    assert analysis["key"] == "C major"


def test_missing_artifacts_return_404(client):
    assert client.get("/api/score/nope").status_code == 404
    assert client.get("/api/analysis/nope").status_code == 404
