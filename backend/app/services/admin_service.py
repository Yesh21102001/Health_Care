"""Admin dashboard data.

Privacy by design: admins see counts, anonymous activity and account details
(name, email, role). They cannot read anyone's conversations or reports; no
endpoint exposes health content to admins. Every admin change is audited.
"""

import re
from datetime import UTC, datetime, timedelta

from bson import ObjectId
from bson.errors import InvalidId
from pymongo.asynchronous.database import AsyncDatabase

from app.core.config import Settings
from app.db.mongo import AI_USAGE, ASSESSMENTS, AUDIT_LOG, CONVERSATIONS, EVENTS, SESSIONS, USERS


async def dashboard(db: AsyncDatabase, settings: Settings) -> dict:
    now = datetime.now(UTC)
    week_ago = now - timedelta(days=7)

    urgency = {r["_id"]: r["count"] async for r in await db[ASSESSMENTS].aggregate([{"$group": {"_id": "$urgency_level", "count": {"$sum": 1}}}])}
    statuses = {r["_id"]: r["count"] async for r in await db[CONVERSATIONS].aggregate([{"$group": {"_id": "$status", "count": {"$sum": 1}}}])}

    usage_rows = [
        r
        async for r in await db[AI_USAGE].aggregate(
            [
                {"$match": {"created_at": {"$gte": week_ago}}},
                {
                    "$group": {
                        "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
                        "requests": {"$sum": 1},
                        "errors": {"$sum": {"$cond": ["$ok", 0, 1]}},
                        "input_tokens": {"$sum": {"$ifNull": ["$input_tokens", 0]}},
                        "output_tokens": {"$sum": {"$ifNull": ["$output_tokens", 0]}},
                        "latency_total": {"$sum": {"$ifNull": ["$latency_ms", 0]}},
                    }
                },
                {"$sort": {"_id": 1}},
            ]
        )
    ]
    total_requests = sum(r["requests"] for r in usage_rows)

    db_ok = True
    try:
        await db.command("ping")
    except Exception:
        db_ok = False

    recent = [
        {"type": e["type"], "urgency": e.get("urgency"), "createdAt": e["created_at"]}
        async for e in db[EVENTS].find({}, {"_id": 0}).sort("created_at", -1).limit(15)
    ]

    return {
        "totals": {
            "users": await db[USERS].count_documents({}),
            "newUsers7d": await db[USERS].count_documents({"created_at": {"$gte": week_ago}}),
            "conversations": await db[CONVERSATIONS].count_documents({}),
            "assessments": await db[ASSESSMENTS].count_documents({}),
            "activeSessions": await db[SESSIONS].count_documents({"expires_at": {"$gt": now}}),
        },
        "assessmentsByUrgency": {k: urgency.get(k, 0) for k in ("self_monitoring", "consultation", "urgent", "emergency")},
        "conversationsByStatus": {k: statuses.get(k, 0) for k in ("in_progress", "completed", "emergency_flagged")},
        "recentActivity": recent,
        "system": {
            "database": "ok" if db_ok else "unreachable",
            "aiConfigured": settings.ai_configured,
            "model": settings.claude_model,
            "environment": settings.environment,
        },
        "aiUsage": {
            "requests7d": total_requests,
            "errors7d": sum(r["errors"] for r in usage_rows),
            "inputTokens7d": sum(r["input_tokens"] for r in usage_rows),
            "outputTokens7d": sum(r["output_tokens"] for r in usage_rows),
            "avgLatencyMs": round(sum(r["latency_total"] for r in usage_rows) / total_requests) if total_requests else 0,
            "byDay": [
                {"date": r["_id"], "requests": r["requests"], "errors": r["errors"], "tokens": r["input_tokens"] + r["output_tokens"]}
                for r in usage_rows
            ],
        },
    }


async def list_users(db: AsyncDatabase, query: str | None, page: int, page_size: int) -> tuple[list[dict], int]:
    filt: dict = {}
    if query:
        q = re.escape(query.strip()[:100])
        filt = {"$or": [{"name": {"$regex": q, "$options": "i"}}, {"email": {"$regex": q, "$options": "i"}}]}
    total = await db[USERS].count_documents(filt)
    cursor = (
        db[USERS]
        .find(filt, {"name": 1, "email": 1, "role": 1, "created_at": 1})
        .sort("created_at", -1)
        .skip((page - 1) * page_size)
        .limit(page_size)
    )
    users = [u async for u in cursor]
    ids = [u["_id"] for u in users]
    counts = {
        r["_id"]: r["count"]
        async for r in await db[CONVERSATIONS].aggregate(
            [{"$match": {"user_id": {"$in": ids}}}, {"$group": {"_id": "$user_id", "count": {"$sum": 1}}}]
        )
    }
    for u in users:
        u["conversation_count"] = counts.get(u["_id"], 0)
    return users, total


class AdminActionError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


async def set_role(db: AsyncDatabase, admin_id: str, target_id: str, role: str) -> dict:
    try:
        oid = ObjectId(target_id)
    except InvalidId:
        raise AdminActionError(404, "User not found.") from None
    if target_id == admin_id and role != "admin":
        raise AdminActionError(400, "You can't remove your own admin access.")
    user = await db[USERS].find_one({"_id": oid}, {"password_hash": 0})
    if not user:
        raise AdminActionError(404, "User not found.")
    previous = user["role"]
    await db[USERS].update_one({"_id": oid}, {"$set": {"role": role, "updated_at": datetime.now(UTC)}})
    await audit(db, admin_id, "user.role_changed", target_id, {"from": previous, "to": role})
    user["role"] = role
    return user


async def audit(db: AsyncDatabase, admin_id: str, action: str, target_id: str | None = None, details: dict | None = None) -> None:
    await db[AUDIT_LOG].insert_one(
        {"admin_id": admin_id, "action": action, "target_id": target_id, "details": details or {}, "created_at": datetime.now(UTC)}
    )


async def audit_entries(db: AsyncDatabase, limit: int = 100) -> list[dict]:
    rows = [r async for r in db[AUDIT_LOG].find({}).sort("created_at", -1).limit(limit)]
    admin_ids = {r["admin_id"] for r in rows} | {r["target_id"] for r in rows if r.get("target_id")}
    oids = []
    for i in admin_ids:
        try:
            oids.append(ObjectId(i))
        except (InvalidId, TypeError):
            pass
    names = {str(u["_id"]): u["email"] async for u in db[USERS].find({"_id": {"$in": oids}}, {"email": 1})}
    return [
        {
            "id": str(r["_id"]),
            "action": r["action"],
            "admin": names.get(r["admin_id"], "deleted user"),
            "target": names.get(r.get("target_id") or "", r.get("target_id")),
            "details": r.get("details", {}),
            "createdAt": r["created_at"],
        }
        for r in rows
    ]
