"""공통 에러 응답 — API 명세서 0장 "에러 응답 형식"

모든 에러는 {"error": {"code", "message", "field"?, "detail"?}} 모양으로 보냄.
message는 화면에 그대로 띄울 수 있는 쉬운 문장.
"""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic.alias_generators import to_camel
from starlette import status
from starlette.exceptions import HTTPException as StarletteHTTPException

DEFAULT_MESSAGES = {
    "VALIDATION_ERROR": "입력한 내용을 다시 확인해 주세요.",
    "UNAUTHORIZED": "로그인이 필요해요.",
    "FORBIDDEN": "이 내용은 볼 수 없어요.",
    "TOKEN_EXPIRED": "로그인이 끝났어요. 다시 로그인해 주세요.",
    "NOT_FOUND": "찾을 수 없어요.",
    "METHOD_NOT_ALLOWED": "지원하지 않는 요청이에요.",
    "TOO_MANY_REQUESTS": "요청이 너무 많아요. 잠시 후 다시 시도해 주세요.",
    "INTERNAL_ERROR": "잠시 문제가 생겼어요. 잠시 후 다시 시도해 주세요.",
}

STATUS_CODES = {
    status.HTTP_400_BAD_REQUEST: "VALIDATION_ERROR",
    status.HTTP_401_UNAUTHORIZED: "UNAUTHORIZED",
    status.HTTP_403_FORBIDDEN: "FORBIDDEN",
    status.HTTP_404_NOT_FOUND: "NOT_FOUND",
    status.HTTP_405_METHOD_NOT_ALLOWED: "METHOD_NOT_ALLOWED",
    status.HTTP_429_TOO_MANY_REQUESTS: "TOO_MANY_REQUESTS",
}


class AppError(Exception):
    """명세서에 적힌 에러 코드로 응답할 때 씀 — raise AppError(401, "AUTH_INVALID_CREDENTIALS", "...")"""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str | None = None,
        *,
        field: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(code)
        self.status_code = status_code
        self.code = code
        self.message = message or DEFAULT_MESSAGES.get(code, DEFAULT_MESSAGES["INTERNAL_ERROR"])
        self.field = field
        self.detail = detail


def error_response(
    status_code: int,
    code: str,
    message: str,
    field: str | None = None,
    detail: dict[str, Any] | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {"code": code, "message": message}
    if field is not None:
        body["field"] = field
    if detail is not None:
        body["detail"] = detail
    return JSONResponse({"error": body}, status_code=status_code)


def _field_name(loc: tuple[Any, ...]) -> str | None:
    """("body", "consents", "sensitive_health") → "consents.sensitiveHealth" """
    parts = [str(p) for p in loc if p not in ("body", "query", "path", "header", "cookie")]
    if not parts:
        return None
    return ".".join(to_camel(p) if "_" in p else p for p in parts)


def _validation_message(err: dict[str, Any]) -> str:
    if err.get("type") == "extra_forbidden":
        return "바꿀 수 없는 항목이에요."
    if err.get("type") == "value_error":
        # validator에서 ValueError("...")로 쓴 쉬운 문장을 그대로 씀
        msg = str(err.get("msg", ""))
        return msg.removeprefix("Value error, ") or DEFAULT_MESSAGES["VALIDATION_ERROR"]
    return DEFAULT_MESSAGES["VALIDATION_ERROR"]


async def _app_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)
    return error_response(exc.status_code, exc.code, exc.message, exc.field, exc.detail)


async def _validation_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    errors = exc.errors()
    first = errors[0] if errors else {}
    return error_response(
        status.HTTP_400_BAD_REQUEST,
        "VALIDATION_ERROR",
        _validation_message(first),
        field=_field_name(tuple(first.get("loc", ()))),
    )


async def _http_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    code = STATUS_CODES.get(exc.status_code, "INTERNAL_ERROR" if exc.status_code >= 500 else "VALIDATION_ERROR")
    return error_response(exc.status_code, code, DEFAULT_MESSAGES[code])


async def _unhandled_error_handler(_: Request, exc: Exception) -> JSONResponse:
    return error_response(status.HTTP_500_INTERNAL_SERVER_ERROR, "INTERNAL_ERROR", DEFAULT_MESSAGES["INTERNAL_ERROR"])


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _app_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, _http_error_handler)
    app.add_exception_handler(Exception, _unhandled_error_handler)
