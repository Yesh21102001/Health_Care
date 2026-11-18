"""Fixed-window rate limiter stored in MongoDB.

Stored in the database (not memory) so limits hold across every server
instance. Identifiers such as IPs and emails are hashed before storage.
"""

import math
import time
from dataclasses import dataclass
from datetime import UTC, datetime

from pymongo import ReturnDocument
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError

from app.core.security import hash_token
from app.db.mongo import RATE_LIMITS


@dataclass(frozen=True)
class RateLimitResult:
    ok: bool
    remaining: int
    retry_after_seconds: int


async def rate_limit(db: AsyncDatabase, scope: str, identifier: str, limit: int, window_seconds: int) -> RateLimitResult:
    now = time.time()
    window_index = math.floor(now / window_seconds)
    key = f"{scope}:{hash_token(identifier)}:{window_index}"
    expires_at = datetime.fromtimestamp((window_index + 1) * window_seconds, tz=UTC)

    async def increment() -> dict | None:
        return await db[RATE_LIMITS].find_one_and_update(
            {"key": key},
            {"$inc": {"count": 1}, "$setOnInsert": {"expires_at": expires_at}},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )

    try:
        doc = await increment()
    except DuplicateKeyError:
        # Two simultaneous first requests can race on the upsert; retrying updates instead.
        doc = await increment()

    count = int(doc["count"]) if doc else 1
    return RateLimitResult(
        ok=count <= limit,
        remaining=max(0, limit - count),
        retry_after_seconds=max(1, math.ceil(expires_at.timestamp() - time.time())),
    )
