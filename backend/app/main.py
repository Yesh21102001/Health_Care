"""HealthAI API entry point.

Run (development):  uvicorn app.main:app --reload --port 8000 --no-server-header
API docs (dev only): http://localhost:8000/docs
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.errors import register_error_handlers
from app.api.middleware import BodySizeLimitMiddleware, CsrfOriginMiddleware, SecurityHeadersMiddleware
from app.api.routes import admin, auth, chat, health, profile
from app.core.config import Settings, get_settings
from app.core.logging import log_info
from app.db import mongo
from app.services.ai_service import ClaudeService
from app.services.events import usage_recorder


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        await mongo.connect(settings)
        log_info("app.started", environment=settings.environment)
        yield
        await mongo.close()

    app = FastAPI(
        title="HealthAI API",
        version="0.1.0",
        lifespan=lifespan,
        # Interactive docs are handy locally but shouldn't be public in production.
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None,
        openapi_url=None if settings.is_production else "/openapi.json",
    )

    register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(chat.router)
    app.include_router(profile.router)
    app.include_router(admin.router)

    # One AI client per process. Tests replace app.state.ai with a fake.
    app.state.ai = ClaudeService(settings, usage_recorder(mongo.get_db))

    # Middleware runs outermost-last-added: size limit -> CSRF -> headers -> app.
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(CsrfOriginMiddleware, settings=settings)
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=settings.max_body_bytes)
    return app


app = create_app()
