"""Consistent error responses: {"error": "...", "fieldErrors": {"field": "message"}}.
Matches what the frontend already expects. Internal details are never sent to clients."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import log_error
from app.schemas.auth import FieldError


class ApiError(Exception):
    def __init__(self, status: int, message: str, field_errors: dict[str, str] | None = None, headers: dict[str, str] | None = None):
        self.status = status
        self.message = message
        self.field_errors = field_errors
        self.headers = headers


def error_response(status: int, message: str, field_errors: dict[str, str] | None = None, headers: dict[str, str] | None = None) -> JSONResponse:
    body: dict = {"error": message}
    if field_errors:
        body["fieldErrors"] = field_errors
    return JSONResponse(body, status_code=status, headers=headers)


def _field_errors(exc: RequestValidationError) -> tuple[dict[str, str], bool]:
    """Returns ({field: message}, is_json_syntax_error)."""
    out: dict[str, str] = {}
    for err in exc.errors():
        if err.get("type") == "json_invalid":
            return {}, True
        ctx_error = (err.get("ctx") or {}).get("error")
        loc = [str(p) for p in err.get("loc", ()) if p != "body"]
        if isinstance(ctx_error, FieldError):
            field, message = ctx_error.field, str(ctx_error)
        else:
            field = loc[-1] if loc else "form"
            message = str(ctx_error) if isinstance(ctx_error, ValueError) else err.get("msg", "Invalid value.")
            if err.get("type") == "missing":
                message = "This field is required."
            elif err.get("type") == "model_attributes_type":
                field, message = "form", "Expected a JSON object."
        out.setdefault(field, message)
    return out, False


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return error_response(exc.status, exc.message, exc.field_errors, exc.headers)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        fields, json_syntax = _field_errors(exc)
        if json_syntax:
            return error_response(400, "Invalid JSON.")
        return error_response(400, "Please fix the highlighted fields.", fields)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        message = exc.detail if isinstance(exc.detail, str) else "Request failed."
        return error_response(exc.status_code, message, headers=getattr(exc, "headers", None))

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        log_error("request.unhandled", exc, path=request.url.path)
        return error_response(500, "Something went wrong. Please try again.")
