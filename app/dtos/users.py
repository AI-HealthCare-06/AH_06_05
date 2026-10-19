"""내 정보 (API U-1 · U-2) — JSON은 camelCase"""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import ConfigDict, Field

from app.core.validators import optional_after_validator, validate_birth_year
from app.dtos.base import CamelModel
from app.models.users import Dialysis, Drinking, Pregnant, Sex, Smoking, User, UserHealthProfile

# 생활습관 팩트표의 질환 10개 (lifestyle_diseases.id, 10/14 회의 3번). 팩트표와 같은지는 test_health_ids.py가 확인
DiseaseId = Literal["HTN", "DM2", "DLP", "CKD", "IHD", "STROKE", "AF", "COPD", "OP", "OA"]


class UpcomingExam(CamelModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, Field(min_length=1, max_length=50)]
    date: date


class HealthUpdate(CamelModel):
    """U-2 health: 보낸 칸만 바꿈. 목록 칸(diseases, upcomingExams)은 보낸 목록으로 통째로 바꿈"""

    model_config = ConfigDict(extra="forbid")

    smoking: Smoking | None = None
    drinking: Drinking | None = None
    diseases: list[DiseaseId] | None = None
    pregnant: Pregnant | None = None
    dialysis: Dialysis | None = None
    height_cm: Annotated[int | None, Field(None, gt=0)]
    weight_kg: Annotated[Decimal | None, Field(None, gt=0, max_digits=4, decimal_places=1)]
    upcoming_exams: list[UpcomingExam] | None = None


class UserUpdateRequest(CamelModel):
    """바꿀 칸만 보냄. email 등 없는 칸을 보내면 VALIDATION_ERROR (U-2)"""

    model_config = ConfigDict(extra="forbid")

    birth_year: Annotated[int | None, Field(None), optional_after_validator(validate_birth_year)]
    sex: Sex | None = None
    health: HealthUpdate | None = None


class UpcomingExamOut(CamelModel):
    name: str
    date: str


class HealthResponse(CamelModel):
    smoking: Smoking
    drinking: Drinking
    diseases: list[str]
    pregnant: Pregnant | None
    dialysis: Dialysis | None
    height_cm: int | None
    weight_kg: float | None
    upcoming_exams: list[UpcomingExamOut]

    @classmethod
    def from_profile(cls, profile: UserHealthProfile) -> "HealthResponse":
        return cls(
            smoking=profile.smoking,
            drinking=profile.drinking,
            diseases=list(profile.diseases),
            pregnant=profile.pregnant,
            dialysis=profile.dialysis,
            height_cm=profile.height_cm,
            weight_kg=float(profile.weight_kg) if profile.weight_kg is not None else None,
            upcoming_exams=[UpcomingExamOut(**e) for e in profile.upcoming_exams],
        )

    def as_json(self) -> dict[str, Any]:
        """분석 시점 스냅샷(analyses.health_snapshot)으로 저장할 때 U-1과 같은 모양"""
        return self.model_dump(mode="json", by_alias=True)


class UserInfoResponse(CamelModel):
    id: int
    email: str
    birth_year: int
    sex: Sex
    created_at: datetime
    health: HealthResponse

    @classmethod
    def from_user(cls, user: User, profile: UserHealthProfile) -> "UserInfoResponse":
        return cls(
            id=user.id,
            email=user.login_id,
            birth_year=user.birth_year,
            sex=user.sex,
            created_at=user.created_at,
            health=HealthResponse.from_profile(profile),
        )
