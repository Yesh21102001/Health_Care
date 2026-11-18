"""Authentication endpoints: /api/auth/*"""

from datetime import datetime
from urllib.parse import quote

from fastapi import APIRouter, Request, Response, status

from app.api.deps import ClientIpDep, CurrentUser, DbDep, SessionTokenDep, SettingsDep
from app.api.errors import ApiError
from app.core.config import Settings
from app.core.logging import log_info
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    OkResponse,
    RegisterRequest,
    ResetPasswordRequest,
    UserResponse,
)
from app.services import auth_service
from app.services.events import record_event
from app.services.mailer import send_password_reset_email
from app.services.rate_limit import rate_limit
from app.services.session_service import create_session, revoke_session

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Same response whether or not the email exists, so this can't be used to discover accounts.
FORGOT_MESSAGE = "If an account exists for that email, we've sent a link to reset the password."
INVALID_RESET = "This reset link is invalid or has expired."


def _too_many(retry_after: int) -> ApiError:
    return ApiError(429, "Too many attempts. Please wait and try again.", headers={"Retry-After": str(retry_after)})


def _set_session_cookie(response: Response, settings: Settings, token: str, expires_at: datetime) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        expires=expires_at,
        path="/",
        httponly=True,  # JavaScript can't read it, so XSS can't steal it
        secure=settings.is_production,
        samesite="lax",  # not sent on cross-site POSTs
    )


def _clear_session_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        key=settings.session_cookie_name, path="/", httponly=True, secure=settings.is_production, samesite="lax"
    )


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=UserResponse)
async def register(body: RegisterRequest, request: Request, response: Response, db: DbDep, settings: SettingsDep, ip: ClientIpDep):
    limit = await rate_limit(db, "register:ip", ip, 10, 60 * 60)
    if not limit.ok:
        raise _too_many(limit.retry_after_seconds)
    try:
        user = await auth_service.register_user(db, body)
    except auth_service.EmailTakenError as exc:
        raise ApiError(409, exc.message, {"email": exc.message}) from None
    token, expires_at = await create_session(db, user.id, settings.session_ttl_seconds, request.headers.get("user-agent"))
    _set_session_cookie(response, settings, token, expires_at)
    log_info("auth.register", user_id=user.id)
    await record_event(db, "user.registered")
    return UserResponse(user=user)


@router.post("/login", response_model=UserResponse)
async def login(body: LoginRequest, request: Request, response: Response, db: DbDep, settings: SettingsDep, ip: ClientIpDep):
    # Per IP (one attacker, many accounts) and per account (many IPs, one account).
    window = 15 * 60
    by_ip = await rate_limit(db, "login:ip", ip, 30, window)
    by_email = await rate_limit(db, "login:email", body.email, 10, window)
    if not by_ip.ok or not by_email.ok:
        raise _too_many(max(by_ip.retry_after_seconds, by_email.retry_after_seconds))

    user = await auth_service.authenticate(db, body.email, body.password)
    if user is None:
        raise ApiError(401, "Incorrect email or password.")  # same message for unknown email / wrong password

    token, expires_at = await create_session(db, user.id, settings.session_ttl_seconds, request.headers.get("user-agent"))
    _set_session_cookie(response, settings, token, expires_at)
    log_info("auth.login", user_id=user.id)
    return UserResponse(user=user)


@router.post("/logout", response_model=OkResponse)
async def logout(response: Response, db: DbDep, settings: SettingsDep, token: SessionTokenDep):
    await revoke_session(db, token)
    _clear_session_cookie(response, settings)
    return OkResponse()


@router.get("/me", response_model=UserResponse)
async def me(user: CurrentUser):
    return UserResponse(user=user)


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(body: ForgotPasswordRequest, db: DbDep, settings: SettingsDep, ip: ClientIpDep):
    by_ip = await rate_limit(db, "forgot:ip", ip, 10, 60 * 60)
    by_email = await rate_limit(db, "forgot:email", body.email, 3, 60 * 60)
    if not by_ip.ok or not by_email.ok:
        raise _too_many(max(by_ip.retry_after_seconds, by_email.retry_after_seconds))

    reset = await auth_service.create_password_reset_token(db, body.email, settings.reset_token_ttl_seconds)
    if reset:
        token, name = reset
        url = f"{settings.frontend_url.rstrip('/')}/reset-password?token={quote(token)}"
        await send_password_reset_email(settings, body.email, name, url)
    return MessageResponse(message=FORGOT_MESSAGE)


@router.post("/reset-password", response_model=OkResponse)
async def reset_password(body: ResetPasswordRequest, response: Response, db: DbDep, settings: SettingsDep, ip: ClientIpDep):
    limit = await rate_limit(db, "reset:ip", ip, 20, 60 * 60)
    if not limit.ok:
        raise _too_many(limit.retry_after_seconds)
    if not 20 <= len(body.token) <= 200 or not await auth_service.reset_password(db, body.token, body.password):
        raise ApiError(400, INVALID_RESET)
    log_info("auth.password_reset")
    _clear_session_cookie(response, settings)  # every session was revoked; sign in fresh
    return OkResponse()
