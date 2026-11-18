"""Shapes for conversations, assessments, profile and admin data.

Output models serialize in camelCase to match the frontend's TypeScript types
(types/health.ts). Input models accept camelCase.
"""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field
from pydantic.alias_generators import to_camel

from app.schemas.auth import CamelModel, Email, LoginPassword, Name, NewPassword, AnyString, FieldError
from pydantic import model_validator

UrgencyLevel = Literal["self_monitoring", "consultation", "urgent", "emergency"]
ConversationStatus = Literal["in_progress", "completed", "emergency_flagged"]

URGENCY_ORDER: dict[str, int] = {"self_monitoring": 0, "consultation": 1, "urgent": 2, "emergency": 3}


class CamelOut(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, serialize_by_alias=True)


# ---------------- chat ----------------


def _message_text(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Type a message first.")
    return value.strip()


class ChatRequest(CamelModel):
    conversation_id: str | None = None
    message: Annotated[str, BeforeValidator(_message_text)]


class MessageOut(CamelOut):
    id: str
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime


class ConversationOut(CamelOut):
    id: str
    title: str
    status: ConversationStatus
    created_at: datetime
    updated_at: datetime
    assessment_id: str | None = None
    messages: list[MessageOut]
    can_generate_report: bool = False


class ConversationSummary(CamelOut):
    id: str
    title: str
    status: ConversationStatus
    created_at: datetime
    updated_at: datetime
    assessment_id: str | None = None
    message_count: int


class ChatResponse(CamelOut):
    conversation: ConversationOut
    assessment_id: str | None = None


class ConversationListResponse(CamelOut):
    conversations: list[ConversationSummary]


class ConversationResponse(CamelOut):
    conversation: ConversationOut


# ---------------- assessments ----------------


class PossibleExplanation(CamelOut):
    name: str
    why: str


class AssessmentOut(CamelOut):
    id: str
    conversation_id: str
    created_at: datetime
    symptoms: list[str]
    duration: str
    severity: str
    additional_info: list[str]
    possible_explanations: list[PossibleExplanation]
    warning_signs: list[str]
    next_steps: list[str]
    urgency_level: UrgencyLevel
    urgency_reason: str


class AssessmentRequest(CamelModel):
    conversation_id: AnyString


class AssessmentResponse(CamelOut):
    assessment: AssessmentOut


class AssessmentListResponse(CamelOut):
    assessments: list[AssessmentOut]


# ---------------- profile ----------------

RetentionDays = Literal[30, 90, 365] | None


class PrivacyOut(CamelOut):
    health_data_consent: bool
    consented_at: datetime | None = None
    retention_days: RetentionDays = None


class ProfileOut(CamelOut):
    id: str
    name: str
    email: str
    role: Literal["user", "admin"]
    member_since: datetime
    privacy: PrivacyOut


class ProfileResponse(CamelOut):
    profile: ProfileOut


class UpdateProfileRequest(CamelModel):
    name: Name
    email: Email
    # Required only when changing the email address.
    current_password: str | None = Field(default=None, max_length=128)


class ChangePasswordRequest(CamelModel):
    current_password: LoginPassword
    new_password: NewPassword
    confirm_password: AnyString

    @model_validator(mode="after")
    def _check(self) -> "ChangePasswordRequest":
        if self.new_password != self.confirm_password:
            raise FieldError("confirmPassword", "Passwords do not match.")
        if self.new_password == self.current_password:
            raise FieldError("newPassword", "Choose a password different from your current one.")
        return self


class UpdatePrivacyRequest(CamelModel):
    health_data_consent: bool
    retention_days: RetentionDays = None


class DeleteAccountRequest(CamelModel):
    password: LoginPassword


# ---------------- admin ----------------


class AdminUserOut(CamelOut):
    id: str
    name: str
    email: str
    role: Literal["user", "admin"]
    created_at: datetime
    conversation_count: int


class AdminUsersResponse(CamelOut):
    users: list[AdminUserOut]
    total: int
    page: int
    page_size: int


class UpdateRoleRequest(CamelModel):
    role: Literal["user", "admin"]
