"""회원가입 · 로그인 · 출입증 다시 받기 (API A-1 · A-2 · A-4) — JSON은 camelCase"""

from typing import Annotated

from pydantic import AfterValidator, ConfigDict, EmailStr, Field

from app.core.validators import validate_birth_year, validate_password
from app.dtos.base import CamelModel
from app.models.users import Drinking, Sex, Smoking


class SignUpConsents(CamelModel):
    """세 개 모두 true여야 가입 가능 (false면 CONSENT_REQUIRED)"""

    terms: bool
    privacy: bool
    sensitive_health: bool


class SignUpHealth(CamelModel):
    """가입 때 받는 건강 정보 (흡연, 음주만, 10/14 회의). 나머지는 내 정보(U-2)에서"""

    model_config = ConfigDict(extra="forbid")

    smoking: Smoking
    drinking: Drinking


class SignUpRequest(CamelModel):
    """별명은 받지 않음 (#96). 없는 칸을 보내면 VALIDATION_ERROR"""

    model_config = ConfigDict(extra="forbid")

    email: Annotated[EmailStr, Field(max_length=100)]
    password: Annotated[str, AfterValidator(validate_password)]
    birth_year: Annotated[int, AfterValidator(validate_birth_year)]
    sex: Sex
    health: SignUpHealth
    consents: SignUpConsents


class LoginRequest(CamelModel):
    email: EmailStr
    password: Annotated[str, Field(min_length=1)]


class UserSummary(CamelModel):
    """건강 정보는 넣지 않음 (로그인 때마다 민감정보를 보내지 않음). 건강 정보는 U-1"""

    id: int
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
