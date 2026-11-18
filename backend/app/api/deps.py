"""Shared FastAPI dependencies."""

from typing import Annotated

from fastapi import Depends, Request
from pymongo.asynchronous.database import AsyncDatabase

from app.api.errors import ApiError
from app.core.config import Settings, get_settings
from app.db.mongo import get_db
from app.schemas.auth import PublicUser
from app.services.ai_service import AIProvider
from app.services.session_service import get_user_by_session_token

SettingsDep = Annotated[Settings, Depends(get_settings)]
DbDep = Annotated[AsyncDatabase, Depends(get_db)]


def client_ip(request: Request, settings: SettingsDep) -> str:
    """Best-effort client IP. X-Forwarded-For is only trusted behind a proxy we control."""
    if settings.trust_proxy:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


ClientIpDep = Annotated[str, Depends(client_ip)]


def session_token(request: Request, settings: SettingsDep) -> str | None:
    return request.cookies.get(settings.session_cookie_name)


SessionTokenDep = Annotated[str | None, Depends(session_token)]


async def current_user(db: DbDep, token: SessionTokenDep) -> PublicUser:
    """The signed-in user, checked against the database on every request."""
    user = await get_user_by_session_token(db, token)
    if user is None:
        raise ApiError(401, "Not signed in.")
    return user


async def admin_user(user: Annotated[PublicUser, Depends(current_user)]) -> PublicUser:
    """Role comes from the database, never from the client."""
    if user.role != "admin":
        raise ApiError(403, "Admin access required.")
    return user


CurrentUser = Annotated[PublicUser, Depends(current_user)]
AdminUser = Annotated[PublicUser, Depends(admin_user)]


def get_ai(request: Request) -> AIProvider:
    """The AI provider set at startup (tests replace it with a fake)."""
    return request.app.state.ai


AIDep = Annotated[AIProvider, Depends(get_ai)]
