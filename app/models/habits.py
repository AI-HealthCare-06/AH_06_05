"""피처 4 실천 (ERD 4장 recommendations, habit_goals, habit_records). 포인트(rewards)는 뒤로 미룸"""

from enum import StrEnum
from typing import TYPE_CHECKING

from tortoise import fields, models

if TYPE_CHECKING:
    from app.models.analysis import Analysis
    from app.models.users import User


class GoalType(StrEnum):
    CHECK = "check"
    QUANTITY = "quantity"


class HabitStatus(StrEnum):
    ACTIVE = "active"
    ENDED = "ended"


class Recommendation(models.Model):
    """분석으로 고른 실천 추천 (P-1). 분석을 지우면 같이 지워지고, 이걸 가리키던 목표는 연결만 비움 (R-8)"""

    id = fields.BigIntField(primary_key=True)
    analysis: fields.ForeignKeyRelation["Analysis"] = fields.ForeignKeyField(
        "models.Analysis", related_name="recommendations", on_delete=fields.CASCADE
    )
    challenge_key = fields.CharField(max_length=20, description="soup / walk / alcohol (services/challenges.py)")
    title = fields.CharField(max_length=100)
    desc = fields.CharField(max_length=200, null=True, description="팩트표 글 그대로 (예: 하루 소금 5g 이하)")
    reason_label = fields.CharField(max_length=50, description="고혈압, 약과 함께 등 (화면 라벨, 질환 정보)")
    caution_label = fields.CharField(max_length=20, null=True, description="의료진이 정한 강도로 (허혈성심질환 걷기)")
    goal_type = fields.CharEnumField(enum_type=GoalType, max_length=20)
    target_value = fields.DecimalField(max_digits=10, decimal_places=2, null=True)
    unit = fields.CharField(max_length=20, null=True)
    # 팩트표가 JSON 파일이라 ERD의 lifestyle_guides 등을 가리키는 칸 대신 "질환 id:항목 이름"을 적음 (10/30)
    fact_refs: list[str] = fields.JSONField(default=list)
    rank = fields.SmallIntField()
    created_at = fields.DatetimeField(auto_now_add=True)
    analysis_id: int  # 외래 키 칸 (타입 검사용)

    class Meta:
        table = "recommendations"
        unique_together = (("analysis", "challenge_key"),)


class HabitGoal(models.Model):
    """사용자가 고른 실천 목표 (P-2). 활성 목표는 최대 3개 (REQ-111)"""

    id = fields.BigIntField(primary_key=True)
    user: fields.ForeignKeyRelation["User"] = fields.ForeignKeyField(
        "models.User", related_name="habit_goals", on_delete=fields.CASCADE
    )
    recommendation: fields.ForeignKeyNullableRelation[Recommendation] = fields.ForeignKeyField(
        "models.Recommendation", related_name="goals", null=True, on_delete=fields.SET_NULL
    )
    title = fields.CharField(max_length=100)
    goal_type = fields.CharEnumField(enum_type=GoalType, max_length=20)
    target_value = fields.DecimalField(max_digits=10, decimal_places=2, null=True)
    unit = fields.CharField(max_length=20, null=True)
    start_date = fields.DateField()
    end_date = fields.DateField(null=True, description="끝낸 날 (새로 고르거나 동의 철회)")
    status = fields.CharEnumField(enum_type=HabitStatus, max_length=20, default=HabitStatus.ACTIVE)
    created_at = fields.DatetimeField(auto_now_add=True)
    recommendation_id: int | None  # 외래 키 칸 (타입 검사용)

    class Meta:
        table = "habit_goals"


class HabitRecord(models.Model):
    """하루 실천 기록 (P-4). 수량형은 그날 쌓인 값"""

    id = fields.BigIntField(primary_key=True)
    goal: fields.ForeignKeyRelation[HabitGoal] = fields.ForeignKeyField(
        "models.HabitGoal", related_name="records", on_delete=fields.CASCADE
    )
    record_date = fields.DateField()
    value = fields.DecimalField(max_digits=10, decimal_places=2, null=True)
    completed = fields.BooleanField(default=False)
    created_at = fields.DatetimeField(auto_now_add=True)
    goal_id: int  # 외래 키 칸 (타입 검사용)

    class Meta:
        table = "habit_records"
        unique_together = (("goal", "record_date"),)
