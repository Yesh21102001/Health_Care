"""Account logic: registration, sign-in and password reset."""

from datetime import UTC, datetime, timedelta

from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError

from app.core.security import generate_token, get_dummy_hash, hash_password, hash_token, verify_password
from app.db.mongo import RESET_TOKENS, USERS
from app.schemas.auth import PublicUser, RegisterRequest
from app.services.session_service import revoke_all_sessions, to_public_user

# Bump when the Terms/Privacy text changes materially, so users can be asked to re-accept.
CURRENT_TERMS_VERSION = "2026-11-18"


class EmailTakenError(Exception):
    message = "An account with this email already exists."


async def register_user(db: AsyncDatabase, data: RegisterRequest) -> PublicUser:
    now = datetime.now(UTC)
    doc = {
        "name": data.name,
        "email": data.email,  # already trimmed + lowercased by the schema
        "password_hash": await hash_password(data.password),
        "role": "user",  # never taken from input
        "consent": {"terms_accepted_at": now, "terms_version": CURRENT_TERMS_VERSION, "age_confirmed": True},
        # Storing health information needs its own explicit consent, asked before the first chat.
        "privacy": {"health_data_consent": False, "consented_at": None, "retention_days": None},
        "created_at": now,
        "updated_at": now,
    }
    try:
        result = await db[USERS].insert_one(doc)
    except DuplicateKeyError:
        # The unique index is the source of truth (no race between "check" and "insert").
        raise EmailTakenError() from None
    doc["_id"] = result.inserted_id
    return to_public_user(doc)


async def authenticate(db: AsyncDatabase, email: str, password: str) -> PublicUser | None:
    user = await db[USERS].find_one({"email": email})
    if not user:
        await verify_password(password, await get_dummy_hash())  # equalise timing
        return None
    if not await verify_password(password, user["password_hash"]):
        return None
    return to_public_user(user)


async def create_password_reset_token(db: AsyncDatabase, email: str, ttl_seconds: int) -> tuple[str, str] | None:
    """Returns (token, name) if the account exists, else None. Callers must respond identically either way."""
    user = await db[USERS].find_one({"email": email}, {"name": 1})
    if not user:
        return None
    await db[RESET_TOKENS].delete_many({"user_id": user["_id"]})  # only the newest link works
    token = generate_token()
    now = datetime.now(UTC)
    await db[RESET_TOKENS].insert_one(
        {
            "token_hash": hash_token(token),
            "user_id": user["_id"],
            "expires_at": now + timedelta(seconds=ttl_seconds),
            "created_at": now,
        }
    )
    return token, user["name"]


async def reset_password(db: AsyncDatabase, token: str, new_password: str) -> bool:
    """Single-use: the token is deleted atomically as it is consumed."""
    record = await db[RESET_TOKENS].find_one_and_delete(
        {"token_hash": hash_token(token), "expires_at": {"$gt": datetime.now(UTC)}}
    )
    if not record:
        return False
    now = datetime.now(UTC)
    result = await db[USERS].update_one(
        {"_id": record["user_id"]},
        {"$set": {"password_hash": await hash_password(new_password), "password_changed_at": now, "updated_at": now}},
    )
    if result.matched_count == 0:
        return False
    await revoke_all_sessions(db, record["user_id"])  # sign out everywhere
    return True
