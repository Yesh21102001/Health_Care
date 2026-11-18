"""Request/response models for authentication.

JSON uses camelCase (confirmPassword) to match the frontend; Python uses snake_case.
Error messages match the frontend's own validation so users see the same text.
Unknown fields (e.g. "role") are ignored, so nobody can self-assign admin.
"""

from typing import Annotated, Literal

from email_validator import EmailNotValidError, validate_email
from pydantic import BaseModel, BeforeValidator, ConfigDict, model_validator
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="ignore")


class FieldError(ValueError):
    """A validation error that belongs to a specific (camelCase) field.
    Used by model-level checks such as "passwords match"."""

    def __init__(self, field: str, message: str) -> None:
        super().__init__(message)
        self.field = field


# ---------- reusable field types ----------


def _email(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("Enter a valid email address.")
    email = value.strip().lower()
    if len(email) > 254:
        raise ValueError("Email is too long.")
    try:
        validate_email(email, check_deliverability=False)  # syntax only, no DNS lookups
    except EmailNotValidError:
        raise ValueError("Enter a valid email address.") from None
    return email


def _new_password(value: object) -> str:
    # NIST SP 800-63B: favour length over composition rules.
    if not isinstance(value, str) or len(value) < 8:
        raise ValueError("Password must be at least 8 characters.")
    if len(value) > 128:
        raise ValueError("Password must be 128 characters or fewer.")
    return value


def _login_password(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("Enter your password.")
    if len(value) > 128:
        raise ValueError("Password must be 128 characters or fewer.")
    return value


def _name(value: object) -> str:
    if not isinstance(value, str) or len(value.strip()) < 2:
        raise ValueError("Enter your full name.")
    if len(value.strip()) > 80:
        raise ValueError("Name must be 80 characters or fewer.")
    return value.strip()


def _consent(value: object) -> bool:
    if value is not True:
        raise ValueError("You must confirm you are 18+ and accept the Terms and Privacy Policy.")
    return True


def _any_string(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("This field is required.")
    return value


Email = Annotated[str, BeforeValidator(_email)]
NewPassword = Annotated[str, BeforeValidator(_new_password)]
LoginPassword = Annotated[str, BeforeValidator(_login_password)]
Name = Annotated[str, BeforeValidator(_name)]
Consent = Annotated[bool, BeforeValidator(_consent)]
AnyString = Annotated[str, BeforeValidator(_any_string)]


# ---------- requests ----------


class RegisterRequest(CamelModel):
    name: Name
    email: Email
    password: NewPassword
    confirm_password: AnyString
    consent: Consent

    @model_validator(mode="after")
    def _passwords_match(self) -> "RegisterRequest":
        if self.password != self.confirm_password:
            raise FieldError("confirmPassword", "Passwords do not match.")
        return self


class LoginRequest(CamelModel):
    email: Email
    password: LoginPassword


class ForgotPasswordRequest(CamelModel):
    email: Email


class ResetPasswordRequest(CamelModel):
    token: AnyString
    password: NewPassword
    confirm_password: AnyString

    @model_validator(mode="after")
    def _passwords_match(self) -> "ResetPasswordRequest":
        if self.password != self.confirm_password:
            raise FieldError("confirmPassword", "Passwords do not match.")
        return self


# ---------- responses ----------


class PublicUser(BaseModel):
    """The only user shape that ever leaves the server."""

    id: str
    name: str
    email: str
    role: Literal["user", "admin"]


class UserResponse(BaseModel):
    user: PublicUser


class MessageResponse(BaseModel):
    message: str


class OkResponse(BaseModel):
    ok: bool = True
