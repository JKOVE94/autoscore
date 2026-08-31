"""Application configuration loaded from environment / .env."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    storage_dir: str = "storage"
    max_upload_mb: int = 100

    # Stemdeck
    stemdeck_bin: str = "stemdeck"
    stemdeck_args: str = ""
    stem_fallback: str = "none"  # none | demucs

    # Audiveris
    audiveris_bin: str = "audiveris"
    java_bin: str = "java"
    omr_timeout: int = 600

    torch_device: str = "mps"

    # --- Step 2: audio analysis ---
    analysis_sample_rate: int = 22050
    quantize_division: int = 16          # grid resolution (16 = sixteenth notes)
    default_time_signature: str = "4/4"
    melody_fmin_hz: float = 65.41        # C2
    melody_fmax_hz: float = 1046.5       # C6
    min_note_sec: float = 0.08           # discard shorter melody blips
    chord_change_min_beats: int = 1      # min chord duration in beats
    prefer_backends: bool = True         # try basic-pitch/essentia/madmom before fallbacks

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def storage_path(self) -> Path:
        p = Path(self.storage_dir)
        if not p.is_absolute():
            p = BACKEND_ROOT / p
        return p

    @property
    def uploads_path(self) -> Path:
        return self.storage_path / "uploads"

    @property
    def stems_path(self) -> Path:
        return self.storage_path / "stems"

    @property
    def outputs_path(self) -> Path:
        return self.storage_path / "outputs"

    @property
    def stemdeck_arg_list(self) -> list[str]:
        return [a for a in self.stemdeck_args.split(" ") if a]

    def ensure_dirs(self) -> None:
        for d in (self.uploads_path, self.stems_path, self.outputs_path):
            d.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_dirs()
    return settings
