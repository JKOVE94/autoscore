"""FastAPI application entry point.

When a built web UI is present (``STATIC_DIR``, populated by the Docker image or
``./run start``), it is served from the same origin as the API, so the whole app
is one process on one port. In dev (``./run dev``) there is no bundle and the
Vite server proxies ``/api`` instead.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import analyze, build, compress, health, jobs, regenerate, upload
from app.config import Settings, get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging, get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    logger.info("autoscore starting (env=%s)", settings.app_env)
    yield


def _mount_web_ui(app: FastAPI, settings: Settings) -> None:
    static_dir = settings.static_path
    if not (static_dir.is_dir() and (static_dir / "index.html").is_file()):
        logger.info("no bundled web UI at %s — API only (dev uses the Vite server)", static_dir)
        return
    # mounted last so /api/*, /health and /docs keep priority; html=True serves
    # index.html for "/" and 404s unknown paths (the UI is a single page).
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="web")
    logger.info("serving bundled web UI from %s", static_dir)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(
        title="AutoScore — Interactive Lead Sheet Pipeline",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(app)
    for router in (
        health.router,
        upload.router,
        analyze.router,
        build.router,
        jobs.router,
        regenerate.router,
        compress.router,
    ):
        app.include_router(router)
    _mount_web_ui(app, settings)
    return app


app = create_app()
