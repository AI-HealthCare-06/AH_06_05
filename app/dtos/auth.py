"""회원가입 · 로그인 · 출입증 다시 받기 (API A-1 · A-2 · A-4) — JSON은 camelCase"""

from typing import Annotated

from pydantic import AfterValidator, EmailStr, Field

from app.core.validators import validate_birth_year, validate_password
from app.dtos.base import CamelModel
from app.models.users import Sex


class SignUpConsents(CamelModel):
    """세 개 모두 true여야 가입 가능 (false면 CONSENT_REQUIRED)"""

    terms: bool
    privacy: bool
    sensitive_health: bool


class SignUpRequest(CamelModel):
    email: Annotated[EmailStr, Field(max_length=100)]
    password: Annotated[str, AfterValidator(validate_password)]
    nickname: Annotated[str | None, Field(None, max_length=50)]
    birth_year: Annotated[int, AfterValidator(validate_birth_year)]
    sex: Sex
    consents: SignUpConsents


class LoginRequest(CamelModel):
    email: EmailStr
    password: Annotated[str, Field(min_length=1)]


class UserSummary(CamelModel):
    id: int
    nickname: str | None
    birth_year: int
    sex: Sex


class AuthTokensResponse(CamelModel):
    """A-1 회원가입 · A-2 로그인 응답 — 출입증(60분) · 재발급권(14일) · 내 정보"""

    access_token: str
    refresh_token: str
    user: UserSummary


class TokenRefreshRequest(CamelModel):
    refresh_token: str | None = None


class TokenRefreshResponse(CamelModel):
    access_token: str
