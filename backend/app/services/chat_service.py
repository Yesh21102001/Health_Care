"""Conversation flow: safety screen -> AI turn -> output filter -> (report).

All reads and writes are scoped by user_id, so a user can only ever reach
their own conversations. Unknown or foreign IDs behave identically (not found).
"""

import secrets
from datetime import UTC, datetime, timedelta

from bson import ObjectId
from bson.errors import InvalidId
from pymongo import ReturnDocument
from pymongo.asynchronous.database import AsyncDatabase

from app.core.config import Settings
from app.core.logging import log_info
from app.db.mongo import ASSESSMENTS, CONVERSATIONS, USERS
from app.schemas.health import AssessmentOut, ConversationOut, ConversationSummary, MessageOut, URGENCY_ORDER
from app.services import safety_service
from app.services.ai_service import AIProvider
from app.services.events import record_event

DEFAULT_TITLE = "New assessment"


class NotFoundError(Exception):
    pass


class ConsentRequiredError(Exception):
    pass


class ConversationClosedError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotEnoughInformationError(Exception):
    pass


def _oid(value: str | None) -> ObjectId:
    try:
        return ObjectId(value)
    except (InvalidId, TypeError):
        raise NotFoundError() from None


def _now() -> datetime:
    return datetime.now(UTC)


def _expiry(user: dict, from_time: datetime) -> datetime | None:
    days = (user.get("privacy") or {}).get("retention_days")
    return from_time + timedelta(days=days) if days else None


def _user_message_count(conv: dict) -> int:
    return sum(1 for m in conv["messages"] if m["role"] == "user")


def _history(conv: dict) -> list[dict[str, str]]:
    return [{"role": m["role"], "content": m["content"]} for m in conv["messages"]]


def _safety_note(conv: dict) -> str | None:
    floor = conv.get("urgency_floor")
    if floor == "urgent":
        return (
            "Earlier in this conversation the person mentioned a warning sign that needs prompt medical care "
            f"({', '.join(conv.get('safety_labels', []))}). Recommend they seek care urgently, today, while continuing to help."
        )
    return None


def conversation_out(conv: dict, settings: Settings) -> ConversationOut:
    return ConversationOut(
        id=str(conv["_id"]),
        title=conv["title"],
        status=conv["status"],
        created_at=conv["created_at"],
        updated_at=conv["updated_at"],
        assessment_id=str(conv["assessment_id"]) if conv.get("assessment_id") else None,
        messages=[MessageOut(**m) for m in conv["messages"]],
        can_generate_report=conv["status"] == "in_progress"
        and _user_message_count(conv) >= settings.min_user_messages_for_report,
    )


def summary_out(conv: dict) -> ConversationSummary:
    return ConversationSummary(
        id=str(conv["_id"]),
        title=conv["title"],
        status=conv["status"],
        created_at=conv["created_at"],
        updated_at=conv["updated_at"],
        assessment_id=str(conv["assessment_id"]) if conv.get("assessment_id") else None,
        message_count=len(conv.get("messages", [])),
    )


def assessment_out(doc: dict) -> AssessmentOut:
    return AssessmentOut(
        id=str(doc["_id"]),
        conversation_id=str(doc["conversation_id"]),
        created_at=doc["created_at"],
        symptoms=doc["symptoms"],
        duration=doc["duration"],
        severity=doc["severity"],
        additional_info=doc["additional_info"],
        possible_explanations=doc["possible_explanations"],
        warning_signs=doc["warning_signs"],
        next_steps=doc["next_steps"],
        urgency_level=doc["urgency_level"],
        urgency_reason=doc["urgency_reason"],
    )


def _msg(role: str, content: str) -> dict:
    return {"id": secrets.token_hex(8), "role": role, "content": content, "created_at": _now()}


async def _store_assessment(db: AsyncDatabase, user: dict, conv: dict, fields: dict) -> ObjectId:
    now = _now()
    doc = {**fields, "user_id": user["_id"], "conversation_id": conv["_id"], "created_at": now}
    if expiry := _expiry(user, now):
        doc["expires_at"] = expiry
    result = await db[ASSESSMENTS].insert_one(doc)
    await record_event(db, "assessment.created", fields["urgency_level"])
    return result.inserted_id


async def _load_user(db: AsyncDatabase, user_id: str) -> dict:
    user = await db[USERS].find_one({"_id": _oid(user_id)}, {"password_hash": 0})
    if not user:
        raise NotFoundError()
    return user


async def get_conversation(db: AsyncDatabase, user_id: str, conversation_id: str) -> dict:
    conv = await db[CONVERSATIONS].find_one({"_id": _oid(conversation_id), "user_id": _oid(user_id)})
    if not conv:
        raise NotFoundError()
    return conv


async def list_conversations(db: AsyncDatabase, user_id: str, query: str | None = None, limit: int = 100) -> list[dict]:
    filt: dict = {"user_id": _oid(user_id)}
    if query:
        import re

        filt["title"] = {"$regex": re.escape(query.strip()[:100]), "$options": "i"}
    cursor = db[CONVERSATIONS].find(filt, {"messages.content": 0}).sort("updated_at", -1).limit(limit)
    return [c async for c in cursor]


async def delete_conversation(db: AsyncDatabase, user_id: str, conversation_id: str) -> None:
    conv = await get_conversation(db, user_id, conversation_id)
    await db[ASSESSMENTS].delete_many({"conversation_id": conv["_id"], "user_id": conv["user_id"]})
    await db[CONVERSATIONS].delete_one({"_id": conv["_id"], "user_id": conv["user_id"]})


async def send_message(
    db: AsyncDatabase, settings: Settings, ai: AIProvider, user_id: str, conversation_id: str | None, text: str
) -> tuple[dict, ObjectId | None]:
    """Returns (conversation, new_assessment_id_or_None)."""
    user = await _load_user(db, user_id)
    if not (user.get("privacy") or {}).get("health_data_consent"):
        raise ConsentRequiredError()

    text = text[: settings.max_message_chars]
    now = _now()

    if conversation_id:
        conv = await get_conversation(db, user_id, conversation_id)
        if conv["status"] == "emergency_flagged":
            raise ConversationClosedError(
                "This conversation was paused because emergency care was advised. If you're safe, start a new assessment."
            )
        if conv["status"] == "completed":
            raise ConversationClosedError("This assessment is complete. Start a new assessment for new symptoms.")
        if _user_message_count(conv) >= settings.max_user_messages_per_conversation:
            raise ConversationClosedError("This conversation has reached its limit. Please generate your report or start a new one.")
    else:
        conv = {
            "user_id": user["_id"],
            "title": DEFAULT_TITLE,
            "status": "in_progress",
            "messages": [],
            "created_at": now,
            "updated_at": now,
        }
        if expiry := _expiry(user, now):
            conv["expires_at"] = expiry
        conv["_id"] = (await db[CONVERSATIONS].insert_one(conv)).inserted_id
        await record_event(db, "conversation.started")

    conv["messages"].append(_msg("user", text))

    # 1) Deterministic safety screen BEFORE any AI call.
    screen = safety_service.screen_user_message(text)
    if screen.is_emergency:
        conv["messages"].append(_msg("assistant", safety_service.emergency_reply(screen)))
        conv["status"] = "emergency_flagged"
        if conv["title"] == DEFAULT_TITLE:
            conv["title"] = "Emergency guidance given"
        assessment_id = await _store_assessment(db, user, conv, safety_service.emergency_report_fields(screen))
        conv["assessment_id"] = assessment_id
        await _save(db, user, conv)
        await record_event(db, "emergency.flagged")
        log_info("safety.emergency", categories=",".join(screen.categories))
        return conv, assessment_id

    if screen.level == "urgent":
        conv["urgency_floor"] = "urgent"
        conv["safety_labels"] = sorted(set(conv.get("safety_labels", [])) | set(screen.labels))

    # 2) AI turn. If it fails, roll back this message so a retry doesn't duplicate it
    #    (the frontend puts the text back in the input box).
    try:
        turn = await ai.chat_turn(_history(conv), _safety_note(conv))
    except Exception:
        conv["messages"].pop()
        if conv["messages"]:
            await _save(db, user, conv)
        else:
            await db[CONVERSATIONS].delete_one({"_id": conv["_id"], "user_id": user["_id"]})
        raise

    # 3) Output filter on the AI's words.
    filtered = safety_service.filter_ai_reply(turn.reply)
    if filtered.removed_dosing or filtered.removed_certainty:
        log_info("safety.output_filtered", dosing=filtered.removed_dosing, certainty=filtered.removed_certainty)
    conv["messages"].append(_msg("assistant", filtered.text))
    if conv["title"] == DEFAULT_TITLE and turn.conversation_title.strip():
        conv["title"] = turn.conversation_title.strip()[:60]

    assessment_id = None
    if turn.ready_for_report and _user_message_count(conv) >= settings.min_user_messages_for_report:
        assessment_id = await _generate_and_store_report(db, ai, user, conv)

    await _save(db, user, conv)
    return conv, assessment_id


async def _generate_and_store_report(db: AsyncDatabase, ai: AIProvider, user: dict, conv: dict) -> ObjectId:
    draft = await ai.generate_report(_history(conv), _safety_note(conv))
    fields = safety_service.enforce_report_rules(draft.model_dump(), conv.get("urgency_floor"))
    assessment_id = await _store_assessment(db, user, conv, fields)
    conv["assessment_id"] = assessment_id
    conv["status"] = "completed"
    return assessment_id


async def create_report_on_request(db: AsyncDatabase, settings: Settings, ai: AIProvider, user_id: str, conversation_id: str) -> ObjectId:
    user = await _load_user(db, user_id)
    conv = await get_conversation(db, user_id, conversation_id)
    if conv.get("assessment_id"):
        return conv["assessment_id"]
    if conv["status"] != "in_progress" or _user_message_count(conv) < settings.min_user_messages_for_report:
        raise NotEnoughInformationError()
    assessment_id = await _generate_and_store_report(db, ai, user, conv)
    await _save(db, user, conv)
    return assessment_id


async def _save(db: AsyncDatabase, user: dict, conv: dict) -> None:
    conv["updated_at"] = _now()
    update = {k: v for k, v in conv.items() if k != "_id"}
    if expiry := _expiry(user, conv["updated_at"]):
        update["expires_at"] = expiry
    await db[CONVERSATIONS].find_one_and_update(
        {"_id": conv["_id"], "user_id": user["_id"]}, {"$set": update}, return_document=ReturnDocument.AFTER
    )


async def get_assessment(db: AsyncDatabase, user_id: str, assessment_id: str) -> dict:
    doc = await db[ASSESSMENTS].find_one({"_id": _oid(assessment_id), "user_id": _oid(user_id)})
    if not doc:
        raise NotFoundError()
    return doc


async def list_assessments(db: AsyncDatabase, user_id: str, limit: int = 50) -> list[dict]:
    cursor = db[ASSESSMENTS].find({"user_id": _oid(user_id)}).sort("created_at", -1).limit(limit)
    return [a async for a in cursor]


def urgency_at_least(level: str, floor: str) -> bool:
    return URGENCY_ORDER[level] >= URGENCY_ORDER[floor]
