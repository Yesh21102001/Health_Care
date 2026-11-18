"""Server-side sessions: random token in an HttpOnly cookie, only its hash in the database.
Because sessions live in the database, logout and password reset revoke them instantly."""

from datetime import UTC, datetime, timedelta

from bson import ObjectId
from bson.errors import InvalidId
from pymongo.asynchronous.database import AsyncDatabase

from app.core.security import generate_token, hash_token
from app.db.mongo import SESSIONS, USERS
from app.schemas.auth import PublicUser


def to_public_user(doc: dict) -> PublicUser:
    return PublicUser(id=str(doc["_id"]), name=doc["name"], email=doc["email"], role=doc["role"])


async def create_session(
    db: AsyncDatabase, user_id: str, ttl_seconds: int, user_agent: str | None = None
) -> tuple[str, datetime]:
    token = generate_token()
    expires_at = datetime.now(UTC) + timedelta(seconds=ttl_seconds)
    await db[SESSIONS].insert_one(
        {
            "token_hash": hash_token(token),
            "user_id": ObjectId(user_id),
            "expires_at": expires_at,
            "user_agent": (user_agent or "")[:256],
            "created_at": datetime.now(UTC),
        }
    )
    return token, expires_at


async def get_user_by_session_token(db: AsyncDatabase, token: str | None) -> PublicUser | None:
    if not token or len(token) > 200:
        return None
    # Check expiry explicitly: MongoDB's TTL cleanup can lag by up to a minute.
    session = await db[SESSIONS].find_one({"token_hash": hash_token(token), "expires_at": {"$gt": datetime.now(UTC)}})
    if not session:
        return None
    user = await db[USERS].find_one({"_id": session["user_id"]}, {"password_hash": 0})
    return to_public_user(user) if user else None


async def revoke_session(db: AsyncDatabase, token: str | None) -> None:
    if token:
        await db[SESSIONS].delete_one({"token_hash": hash_token(token)})


async def revoke_all_sessions(db: AsyncDatabase, user_id: str | ObjectId) -> None:
    try:
        oid = user_id if isinstance(user_id, ObjectId) else ObjectId(user_id)
    except InvalidId:
        return
    await db[SESSIONS].delete_many({"user_id": oid})
