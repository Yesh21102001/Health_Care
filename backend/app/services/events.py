"""Anonymous platform activity for the admin dashboard.

Events carry a type and (sometimes) an urgency level - never a user ID, name,
email or any health content - so the admin activity feed can't be used to
look into an individual's health conversations.
"""

from datetime import UTC, datetime

from pymongo.asynchronous.database import AsyncDatabase

from app.core.logging import log_error
from app.db.mongo import AI_USAGE, EVENTS

EVENT_TYPES = {
    "user.registered",
    "conversation.started",
    "assessment.created",
    "emergency.flagged",
    "account.deleted",
}


async def record_event(db: AsyncDatabase, event_type: str, urgency: str | None = None) -> None:
    try:
        doc = {"type": event_type, "created_at": datetime.now(UTC)}
        if urgency:
            doc["urgency"] = urgency
        await db[EVENTS].insert_one(doc)
    except Exception as exc:  # analytics must never break a user request
        log_error("events.record_failed", exc, event_type=event_type)


def usage_recorder(get_db):
    async def record(usage: dict) -> None:
        try:
            await get_db()[AI_USAGE].insert_one({**usage, "created_at": datetime.now(UTC)})
        except Exception as exc:
            log_error("ai_usage.record_failed", exc)

    return record
