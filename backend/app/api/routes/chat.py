"""Chat, conversations and assessments. Every endpoint is scoped to the signed-in user."""

from fastapi import APIRouter, Query

from app.api.deps import AIDep, CurrentUser, DbDep, SettingsDep
from app.api.errors import ApiError
from app.schemas.health import (
    AssessmentListResponse,
    AssessmentRequest,
    AssessmentResponse,
    ChatRequest,
    ChatResponse,
    ConversationListResponse,
    ConversationResponse,
)
from app.schemas.auth import OkResponse
from app.services import chat_service
from app.services.ai_service import AIInvalidResponseError, AIUnavailableError
from app.services.rate_limit import rate_limit

router = APIRouter(prefix="/api", tags=["chat"])

NOT_FOUND = "Not found."


def _ai_error(exc: Exception) -> ApiError:
    if isinstance(exc, AIUnavailableError):
        return ApiError(503, exc.message)
    return ApiError(502, "The assistant couldn't produce a valid response. Please try again.")


@router.post("/chat", response_model=ChatResponse)
async def chat(body: ChatRequest, user: CurrentUser, db: DbDep, settings: SettingsDep, ai: AIDep):
    if len(body.message) > settings.max_message_chars:
        raise ApiError(400, "Please fix the highlighted fields.", {"message": f"Keep messages under {settings.max_message_chars} characters."})
    burst = await rate_limit(db, "chat:user", user.id, 20, 10 * 60)
    daily = await rate_limit(db, "chat:user:day", user.id, 200, 24 * 60 * 60)
    if not burst.ok or not daily.ok:
        raise ApiError(429, "You're sending messages too quickly. Please wait a moment.", headers={"Retry-After": str(burst.retry_after_seconds)})
    try:
        conv, assessment_id = await chat_service.send_message(db, settings, ai, user.id, body.conversation_id, body.message)
    except chat_service.NotFoundError:
        raise ApiError(404, NOT_FOUND) from None
    except chat_service.ConsentRequiredError:
        raise ApiError(403, "consent_required") from None
    except chat_service.ConversationClosedError as exc:
        raise ApiError(409, exc.message) from None
    except (AIUnavailableError, AIInvalidResponseError) as exc:
        raise _ai_error(exc) from None
    return ChatResponse(
        conversation=chat_service.conversation_out(conv, settings),
        assessment_id=str(assessment_id) if assessment_id else None,
    )


@router.get("/conversations", response_model=ConversationListResponse)
async def list_conversations(user: CurrentUser, db: DbDep, q: str | None = Query(default=None, max_length=100)):
    convs = await chat_service.list_conversations(db, user.id, q)
    return ConversationListResponse(conversations=[chat_service.summary_out(c) for c in convs])


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(conversation_id: str, user: CurrentUser, db: DbDep, settings: SettingsDep):
    try:
        conv = await chat_service.get_conversation(db, user.id, conversation_id)
    except chat_service.NotFoundError:
        raise ApiError(404, NOT_FOUND) from None
    return ConversationResponse(conversation=chat_service.conversation_out(conv, settings))


@router.delete("/conversations/{conversation_id}", response_model=OkResponse)
async def delete_conversation(conversation_id: str, user: CurrentUser, db: DbDep):
    try:
        await chat_service.delete_conversation(db, user.id, conversation_id)
    except chat_service.NotFoundError:
        raise ApiError(404, NOT_FOUND) from None
    return OkResponse()


@router.post("/assessment", response_model=AssessmentResponse)
async def create_assessment(body: AssessmentRequest, user: CurrentUser, db: DbDep, settings: SettingsDep, ai: AIDep):
    limit = await rate_limit(db, "report:user", user.id, 10, 60 * 60)
    if not limit.ok:
        raise ApiError(429, "Too many report requests. Please wait and try again.")
    try:
        assessment_id = await chat_service.create_report_on_request(db, settings, ai, user.id, body.conversation_id)
        doc = await chat_service.get_assessment(db, user.id, str(assessment_id))
    except chat_service.NotFoundError:
        raise ApiError(404, NOT_FOUND) from None
    except chat_service.NotEnoughInformationError:
        raise ApiError(409, "Please answer a few more questions before generating your report.") from None
    except (AIUnavailableError, AIInvalidResponseError) as exc:
        raise _ai_error(exc) from None
    return AssessmentResponse(assessment=chat_service.assessment_out(doc))


@router.get("/assessment/{assessment_id}", response_model=AssessmentResponse)
async def get_assessment(assessment_id: str, user: CurrentUser, db: DbDep):
    try:
        doc = await chat_service.get_assessment(db, user.id, assessment_id)
    except chat_service.NotFoundError:
        raise ApiError(404, NOT_FOUND) from None
    return AssessmentResponse(assessment=chat_service.assessment_out(doc))


@router.get("/assessments", response_model=AssessmentListResponse)
async def list_assessments(user: CurrentUser, db: DbDep):
    docs = await chat_service.list_assessments(db, user.id)
    return AssessmentListResponse(assessments=[chat_service.assessment_out(d) for d in docs])
