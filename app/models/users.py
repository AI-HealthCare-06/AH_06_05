"""회원 (ERD v1.3 사용자 영역, API A-1 · A-2 · U-1 ~ U-5)

최소 수집: 성명 · 주민번호 · 연락처는 받지 않음. 생년월일 대신 출생연도만.
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
    nickname = fields.CharField(max_length=50, null=True, description="선택 입력. 홈 인사말용")
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
