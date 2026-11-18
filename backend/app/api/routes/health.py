"""Liveness/readiness check, used by deployments and the future admin 'System health' panel."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.api.deps import DbDep
from app.core.logging import log_error

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def health(db: DbDep) -> JSONResponse:
    try:
        await db.command("ping")
        return JSONResponse({"status": "ok", "database": "ok"})
    except Exception as exc:  # report, don't crash
        log_error("health.db_failed", exc)
        return JSONResponse({"status": "degraded", "database": "unreachable"}, status_code=503)
