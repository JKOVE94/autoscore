from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import create_app


@pytest.fixture
def client(tmp_settings):
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: tmp_settings
    return TestClient(app)


def test_health_reports_engine_status(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["app_env"] == "test"
    names = {e["name"] for e in body["engines"]}
    assert names == {"stemdeck", "audiveris"}
    # Neither engine is configured in the test environment.
    assert all(e["configured"] is False for e in body["engines"])


def test_upload_rejects_unknown_extension(client):
    resp = client.post(
        "/api/upload",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert resp.status_code == 415
    assert resp.json()["error"]["code"] == "unsupported_media"


def test_upload_stores_audio_and_infers_mode(client):
    resp = client.post(
        "/api/upload",
        files={"file": ("song.wav", b"RIFF....WAVEfmt ", "audio/wav")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] == "single_audio"
    assert body["kind"] == "audio"
    assert body["job_id"]
