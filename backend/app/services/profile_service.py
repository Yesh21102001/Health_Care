"""Profile, password, privacy/consent and account deletion."""

from datetime import UTC, datetime

from bson import ObjectId
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError

from app.core.security import hash_password, hash_token, verify_password
from app.db.mongo import ASSESSMENTS, CONVERSATIONS, RESET_TOKENS, SESSIONS, USERS
from app.schemas.health import PrivacyOut, ProfileOut
from app.services.auth_service import EmailTakenError
from app.services.events import record_event


class WrongPasswordError(Exception):
    pass


class PasswordRequiredError(Exception):
    pass


def profile_out(user: dict) -> ProfileOut:
    privacy = user.get("privacy") or {}
    return ProfileOut(
        id=str(user["_id"]),
        name=user["name"],
        email=user["email"],
        role=user["role"],
        member_since=user["created_at"],
        privacy=PrivacyOut(
            health_data_consent=bool(privacy.get("health_data_consent")),
            consented_at=privacy.get("consented_at"),
            retention_days=privacy.get("retention_days"),
        ),
    )


async def get_user_doc(db: AsyncDatabase, user_id: str, with_hash: bool = False) -> dict:
    projection = None if with_hash else {"password_hash": 0}
    user = await db[USERS].find_one({"_id": ObjectId(user_id)}, projection)
    if not user:
        raise LookupError()
    return user


async def update_profile(db: AsyncDatabase, user_id: str, name: str, email: str, current_password: str | None) -> dict:
    user = await get_user_doc(db, user_id, with_hash=True)
    update: dict = {"name": name, "updated_at": datetime.now(UTC)}
    if email != user["email"]:
        # Changing the login email requires proof of identity.
        if not current_password:
            raise PasswordRequiredError()
        if not await verify_password(current_password, user["password_hash"]):
            raise WrongPasswordError()
        update["email"] = email
    try:
        await db[USERS].update_one({"_id": user["_id"]}, {"$set": update})
    except DuplicateKeyError:
        raise EmailTakenError() from None
    return await get_user_doc(db, user_id)


async def change_password(db: AsyncDatabase, user_id: str, current: str, new: str, keep_session_token: str | None) -> None:
    user = await get_user_doc(db, user_id, with_hash=True)
    if not await verify_password(current, user["password_hash"]):
        raise WrongPasswordError()
    now = datetime.now(UTC)
    await db[USERS].update_one(
        {"_id": user["_id"]},
        {"$set": {"password_hash": await hash_password(new), "password_changed_at": now, "updated_at": now}},
    )
    # Sign out every other device; keep the session that made the change.
    keep = hash_token(keep_session_token) if keep_session_token else None
    await db[SESSIONS].delete_many({"user_id": user["_id"], **({"token_hash": {"$ne": keep}} if keep else {})})


async def update_privacy(db: AsyncDatabase, user_id: str, consent: bool, retention_days: int | None) -> dict:
    """Withdrawing consent deletes all stored health data (conversations and reports)."""
    oid = ObjectId(user_id)
    now = datetime.now(UTC)
    current = await get_user_doc(db, user_id)
    was_consented = bool((current.get("privacy") or {}).get("health_data_consent"))

    privacy = {
        "health_data_consent": consent,
        "consented_at": (current.get("privacy") or {}).get("consented_at") if was_consented and consent else (now if consent else None),
        "retention_days": retention_days if consent else None,
    }
    await db[USERS].update_one({"_id": oid}, {"$set": {"privacy": privacy, "updated_at": now}})

    if not consent:
        await db[CONVERSATIONS].delete_many({"user_id": oid})
        await db[ASSESSMENTS].delete_many({"user_id": oid})
    else:
        # Apply the retention period to data already stored.
        for coll, field in ((CONVERSATIONS, "updated_at"), (ASSESSMENTS, "created_at")):
            if retention_days:
                await db[coll].update_many(
                    {"user_id": oid},
                    [{"$set": {"expires_at": {"$add": [f"${field}", retention_days * 24 * 3600 * 1000]}}}],
                )
            else:
                await db[coll].update_many({"user_id": oid}, {"$unset": {"expires_at": ""}})
    return await get_user_doc(db, user_id)


async def delete_account(db: AsyncDatabase, user_id: str, password: str) -> None:
    user = await get_user_doc(db, user_id, with_hash=True)
    if not await verify_password(password, user["password_hash"]):
        raise WrongPasswordError()
    oid = user["_id"]
    for coll in (CONVERSATIONS, ASSESSMENTS, SESSIONS, RESET_TOKENS):
        await db[coll].delete_many({"user_id": oid})
    await db[USERS].delete_one({"_id": oid})
    await record_event(db, "account.deleted")
