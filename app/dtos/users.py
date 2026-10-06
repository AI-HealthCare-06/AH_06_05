"""내 정보 (API U-1 · U-2) — JSON은 camelCase"""

from datetime import datetime
from typing import Annotated

from pydantic import ConfigDict, Field

from app.core.validators import optional_after_validator, validate_birth_year
from app.dtos.base import CamelModel
from app.models.users import Sex, User


class UserUpdateRequest(CamelModel):
    """바꿀 칸만 보냄. email 등 없는 칸을 보내면 VALIDATION_ERROR (U-2)"""

    model_config = ConfigDict(extra="forbid")

    nickname: Annotated[str | None, Field(None, max_length=50)]
    birth_year: Annotated[int | None, Field(None), optional_after_validator(validate_birth_year)]
    sex: Sex | None = None


class UserInfoResponse(CamelModel):
    id: int
    email: str
    nickname: str | None
    birth_year: int
    sex: Sex
    created_at: datetime

    @classmethod
    def from_user(cls, user: User) -> "UserInfoResponse":
        return cls(
            id=user.id,
            email=user.login_id,
            nickname=user.nickname,
            birth_year=user.birth_year,
            sex=user.sex,
            created_at=user.created_at,
        )
