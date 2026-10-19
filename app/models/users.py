"""회원 (ERD v1.5 초안 사용자 영역, API A-1 · A-2 · U-1 ~ U-5)

최소 수집: 성명 · 주민번호 · 연락처는 받지 않음. 생년월일 대신 출생연도만. 별명도 받지 않음 (#96).
건강 정보는 민감정보라 users와 나눠 user_health_profiles에 둠 (#101).
"""

from datetime import datetime
from enum import StrEnum

from tortoise import fields, models

MAX_LOGIN_FAILURES = 5  # 5번 틀리면 잠금 (CM-01-E1 · E2)
LOCK_MINUTES = 10


class Sex(StrEnum):
    M = "M"
    F = "F"


class ConsentType(StrEnum):
    TERMS = "terms"  # 이용약관
    PRIVACY = "privacy"  # 개인정보 수집 · 이용
    SENSITIVE_HEALTH = "sensitive_health"  # 민감정보(건강) — 철회하면 업로드 · 분석 불가


class User(models.Model):
    id = fields.BigIntField(primary_key=True)
    login_id = fields.CharField(max_length=100, unique=True, description="이메일")
    password_hash = fields.CharField(max_length=255)
    birth_year = fields.SmallIntField(description="노인주의 · 연령금기 판정")
    sex = fields.CharEnumField(enum_type=Sex, max_length=1)
    failed_login_count = fields.SmallIntField(default=0, description="5번 틀리면 잠금")
    locked_until: datetime | None = fields.DatetimeField(null=True, description="잠금 풀리는 시각")
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)
    deleted_at = fields.DatetimeField(null=True, description="탈퇴 시 개인정보를 지우고 시각만 남김")

    class Meta:
        table = "users"


class UserConsent(models.Model):
    """CM-02 가입 동의 · CM-05 동의 내역. ERD 복합 unique (user, consent_type)"""

    id = fields.BigIntField(primary_key=True)
    user: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
        "models.User", related_name="consents", on_delete=fields.CASCADE
    )
    consent_type = fields.CharEnumField(enum_type=ConsentType, max_length=30)
    agreed = fields.BooleanField()
    agreed_at = fields.DatetimeField(null=True)
    withdrawn_at = fields.DatetimeField(null=True)

    class Meta:
        table = "user_consents"
        unique_together = (("user", "consent_type"),)


class Smoking(StrEnum):
    """국민건강영양조사 BS3_1(현재 흡연 여부) + 잘 모르겠어요"""

    DAILY = "daily"
    SOMETIMES = "sometimes"
    PAST = "past"  # 예전에 피웠지만 지금은 안 피움
    NEVER = "never"
    UNKNOWN = "unknown"


class Drinking(StrEnum):
    """국민건강영양조사 BD1_11(최근 1년 음주 빈도) + 잘 모르겠어요"""

    NONE = "none"
    LT_MONTHLY = "lt_monthly"
    MONTHLY = "monthly"
    TWO_FOUR_MONTHLY = "2_4_monthly"
    TWO_THREE_WEEKLY = "2_3_weekly"
    FOUR_PLUS_WEEKLY = "4plus_weekly"
    UNKNOWN = "unknown"


class Pregnant(StrEnum):
    YES = "yes"
    NO = "no"


class Dialysis(StrEnum):
    YES = "yes"
    NO = "no"
    UNKNOWN = "unknown"


class UserHealthProfile(models.Model):
    """건강 정보 (users와 1:1, 가입 때 함께 만듦). 동의 철회 · 탈퇴 때 줄째 지움"""

    user: fields.OneToOneRelation[User] = fields.OneToOneField(
        "models.User", related_name="health_profile", on_delete=fields.CASCADE, primary_key=True
    )
    smoking = fields.CharEnumField(enum_type=Smoking, max_length=20)
    drinking = fields.CharEnumField(enum_type=Drinking, max_length=20)
    diseases: list[str] = fields.JSONField(default=list, description="lifestyle_diseases.id 목록")
    pregnant = fields.CharEnumField(enum_type=Pregnant, max_length=10, null=True, description="여성만")
    dialysis = fields.CharEnumField(enum_type=Dialysis, max_length=10, null=True)
    height_cm = fields.SmallIntField(null=True)
    weight_kg = fields.DecimalField(max_digits=4, decimal_places=1, null=True)
    upcoming_exams: list[dict[str, str]] = fields.JSONField(default=list, description="[{name, date}] 예정 검사")
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "user_health_profiles"
