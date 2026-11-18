"""The signed-in user's own profile, password, privacy settings and account deletion."""

from fastapi import APIRouter, Response

from app.api.deps import CurrentUser, DbDep, SessionTokenDep, SettingsDep
from app.api.errors import ApiError
from app.api.routes.auth import _clear_session_cookie
from app.schemas.auth import OkResponse
from app.schemas.health import (
    ChangePasswordRequest,
    DeleteAccountRequest,
    ProfileResponse,
    UpdatePrivacyRequest,
    UpdateProfileRequest,
)
from app.services import profile_service
from app.services.auth_service import EmailTakenError
from app.services.rate_limit import rate_limit

router = APIRouter(prefix="/api/profile", tags=["profile"])

WRONG_PASSWORD = "Your current password is incorrect."


async def _limit_password_checks(db, user_id: str) -> None:
    limit = await rate_limit(db, "password_check:user", user_id, 10, 15 * 60)
    if not limit.ok:
        raise ApiError(429, "Too many attempts. Please wait and try again.")


@router.get("", response_model=ProfileResponse)
async def get_profile(user: CurrentUser, db: DbDep):
    return ProfileResponse(profile=profile_service.profile_out(await profile_service.get_user_doc(db, user.id)))


@router.put("", response_model=ProfileResponse)
async def update_profile(body: UpdateProfileRequest, user: CurrentUser, db: DbDep):
    if body.email != user.email:
        await _limit_password_checks(db, user.id)
    try:
        doc = await profile_service.update_profile(db, user.id, body.name, body.email, body.current_password)
    except profile_service.PasswordRequiredError:
        raise ApiError(400, "Please fix the highlighted fields.", {"currentPassword": "Enter your password to change your email."}) from None
    except profile_service.WrongPasswordError:
        raise ApiError(400, "Please fix the highlighted fields.", {"currentPassword": WRONG_PASSWORD}) from None
    except EmailTakenError as exc:
        raise ApiError(409, exc.message, {"email": exc.message}) from None
    return ProfileResponse(profile=profile_service.profile_out(doc))


@router.post("/password", response_model=OkResponse)
async def change_password(body: ChangePasswordRequest, user: CurrentUser, db: DbDep, token: SessionTokenDep):
    await _limit_password_checks(db, user.id)
    try:
        await profile_service.change_password(db, user.id, body.current_password, body.new_password, token)
    except profile_service.WrongPasswordError:
        raise ApiError(400, "Please fix the highlighted fields.", {"currentPassword": WRONG_PASSWORD}) from None
    return OkResponse()


@router.put("/privacy", response_model=ProfileResponse)
async def update_privacy(body: UpdatePrivacyRequest, user: CurrentUser, db: DbDep):
    doc = await profile_service.update_privacy(db, user.id, body.health_data_consent, body.retention_days)
    return ProfileResponse(profile=profile_service.profile_out(doc))


@router.delete("", response_model=OkResponse)
async def delete_account(body: DeleteAccountRequest, response: Response, user: CurrentUser, db: DbDep, settings: SettingsDep):
    await _limit_password_checks(db, user.id)
    try:
        await profile_service.delete_account(db, user.id, body.password)
    except profile_service.WrongPasswordError:
        raise ApiError(400, "Please fix the highlighted fields.", {"password": WRONG_PASSWORD}) from None
    _clear_session_cookie(response, settings)
    return OkResponse()
