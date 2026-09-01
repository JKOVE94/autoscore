from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def _app_with_static(tmp_path):
    static = tmp_path / "static"
    (static / "assets").mkdir(parents=True)
    (static / "index.html").write_text("<!doctype html><title>AutoScore</title>")
    (static / "assets" / "app.js").write_text("console.log('ui')")
    settings = Settings(static_dir=str(static), storage_dir=str(tmp_path / "storage"))
    settings.ensure_dirs()
    return create_app(settings=settings)


def test_bundled_ui_served_same_origin_as_api(tmp_path):
    client = TestClient(_app_with_static(tmp_path))

    assert client.get("/").status_code == 200
    assert b"AutoScore" in client.get("/").content
    assert client.get("/assets/app.js").status_code == 200

    # API, health and docs keep priority over the static mount
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/api/analyze/backends").status_code == 200
    assert client.get("/docs").status_code == 200


def test_app_runs_without_a_bundle(tmp_path):
    settings = Settings(static_dir=str(tmp_path / "nope"), storage_dir=str(tmp_path / "storage"))
    settings.ensure_dirs()
    client = TestClient(create_app(settings=settings))
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/").status_code == 404  # no UI mounted in dev
