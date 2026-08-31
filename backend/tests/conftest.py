from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import pytest

from app.config import Settings, get_settings


@pytest.fixture
def tmp_settings(tmp_path, monkeypatch) -> Settings:
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "storage"))
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.delenv("STEMDECK_BIN", raising=False)
    monkeypatch.delenv("AUDIVERIS_BIN", raising=False)
    get_settings.cache_clear()
    settings = Settings(storage_dir=str(tmp_path / "storage"), app_env="test")
    settings.ensure_dirs()
    return settings


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
