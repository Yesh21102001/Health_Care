"""MongoDB connection (PyMongo's native async API) and index setup."""

from pymongo import ASCENDING, DESCENDING, AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase

from app.core.config import Settings

_client: AsyncMongoClient | None = None
_db: AsyncDatabase | None = None

# Collection names in one place.
USERS = "users"
SESSIONS = "sessions"
RESET_TOKENS = "password_reset_tokens"
RATE_LIMITS = "rate_limits"
CONVERSATIONS = "conversations"
ASSESSMENTS = "assessments"
AI_USAGE = "ai_usage"  # token counts and latency only; never content
EVENTS = "events"  # anonymous platform activity for the admin dashboard
AUDIT_LOG = "audit_log"  # admin actions


async def connect(settings: Settings) -> AsyncDatabase:
    """Open the connection pool once at startup and fail fast if MongoDB is unreachable."""
    global _client, _db
    if _db is not None:
        return _db
    _client = AsyncMongoClient(
        settings.mongodb_uri,
        serverSelectionTimeoutMS=10_000,
        tz_aware=True,  # datetimes come back timezone-aware (UTC)
        appname="healthai-backend",
    )
    await _client.admin.command("ping")
    _db = _client[settings.mongodb_db]
    await ensure_indexes(_db)
    return _db


async def close() -> None:
    global _client, _db
    if _client is not None:
        await _client.close()
    _client = None
    _db = None


def get_db() -> AsyncDatabase:
    if _db is None:
        raise RuntimeError("Database not connected. Was the app started with its lifespan?")
    return _db


async def ensure_indexes(db: AsyncDatabase) -> None:
    """Idempotent: safe to run on every startup."""
    await db[USERS].create_index([("email", ASCENDING)], unique=True)

    await db[SESSIONS].create_index([("token_hash", ASCENDING)], unique=True)
    await db[SESSIONS].create_index([("user_id", ASCENDING)])
    # MongoDB deletes documents once expires_at passes (checked about every 60s).
    await db[SESSIONS].create_index([("expires_at", ASCENDING)], expireAfterSeconds=0)

    await db[RESET_TOKENS].create_index([("token_hash", ASCENDING)], unique=True)
    await db[RESET_TOKENS].create_index([("user_id", ASCENDING)])
    await db[RESET_TOKENS].create_index([("expires_at", ASCENDING)], expireAfterSeconds=0)

    await db[RATE_LIMITS].create_index([("key", ASCENDING)], unique=True)
    await db[RATE_LIMITS].create_index([("expires_at", ASCENDING)], expireAfterSeconds=0)

    # Every query on health data is scoped by user_id, so lead indexes with it.
    await db[CONVERSATIONS].create_index([("user_id", ASCENDING), ("updated_at", DESCENDING)])
    # Per-user retention: documents with expires_at are deleted automatically; without it they're kept.
    await db[CONVERSATIONS].create_index([("expires_at", ASCENDING)], expireAfterSeconds=0)
    await db[ASSESSMENTS].create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
    await db[ASSESSMENTS].create_index([("conversation_id", ASCENDING)])
    await db[ASSESSMENTS].create_index([("expires_at", ASCENDING)], expireAfterSeconds=0)

    await db[AI_USAGE].create_index([("created_at", DESCENDING)])
    # Usage stats and anonymous events are kept for 90 days.
    await db[AI_USAGE].create_index([("created_at", ASCENDING)], expireAfterSeconds=90 * 24 * 3600, name="ttl_90d")
    await db[EVENTS].create_index([("created_at", ASCENDING)], expireAfterSeconds=90 * 24 * 3600, name="ttl_90d")
    await db[AUDIT_LOG].create_index([("created_at", DESCENDING)])
