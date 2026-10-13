"""피처 2 RAG 분석 (ERD v1.5 분석 영역, API R-1 ~ R-6)

한 번의 분석 = 처방전 여러 장(최대 5장)을 합쳐서 점검 + 안내문 2개(복약 · 생활습관).
"""

from enum import StrEnum
from typing import TYPE_CHECKING, Any

from tortoise import fields, models

if TYPE_CHECKING:
    from app.models.masters import Disease
    from app.models.ocr import Prescription, PrescriptionItem
    from app.models.users import User


class AnalysisStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class AnalysisStep(StrEnum):
    DRUG_INFO = "drug_info"  # 약 정보 확인
    SAFETY_CHECK = "safety_check"  # 같이 먹으면 안 되는 약 점검
    GUIDE_GENERATION = "guide_generation"  # 안내문 작성


class DiseaseOrigin(StrEnum):
    PRESCRIPTION = "prescription"  # 처방전의 질병분류기호
    USER = "user"  # RG-05-E1에서 직접 고름


class GuideSection(StrEnum):
    MEDICATION = "medication"
    LIFESTYLE = "lifestyle"


class GuideStatus(StrEnum):
    DONE = "done"
    FAILED = "failed"


class Analysis(models.Model):
    id = fields.BigIntField(primary_key=True)
    user: fields.ForeignKeyRelation["User"] = fields.ForeignKeyField(
        "models.User", related_name="analyses", on_delete=fields.CASCADE
    )
    status = fields.CharEnumField(enum_type=AnalysisStatus, max_length=20, default=AnalysisStatus.QUEUED)
    current_step = fields.CharEnumField(enum_type=AnalysisStep, max_length=30, null=True, description="RG-01 진행 단계")
    failed_step = fields.CharEnumField(
        enum_type=AnalysisStep, max_length=30, null=True, description="실패한 단계 (RG-01-E1)"
    )
    error_code = fields.CharField(
        max_length=50, null=True, description="GUIDE_GENERATION_FAILED / SAFETY_CHECK_FAILED / TIMEOUT"
    )
    retry_count = fields.SmallIntField(default=0, description="3회 초과 시 재시도 막음 (REQ-055)")
    user_birth_year = fields.SmallIntField(null=True, description="분석 시점 출생연도 스냅샷")
    started_at = fields.DatetimeField(null=True)
    finished_at = fields.DatetimeField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "analyses"


class AnalysisPrescription(models.Model):
    """분석에 쓴 처방전 (여러 병원 처방전을 한 번에 점검). ERD 복합 PK → id + unique"""

    id = fields.BigIntField(primary_key=True)
    analysis: fields.ForeignKeyRelation[Analysis] = fields.ForeignKeyField(
        "models.Analysis", related_name="prescriptions", on_delete=fields.CASCADE
    )
    prescription: fields.ForeignKeyRelation["Prescription"] = fields.ForeignKeyField(
        "models.Prescription", related_name="analyses", on_delete=fields.CASCADE
    )

    class Meta:
        table = "analysis_prescriptions"
        unique_together = (("analysis", "prescription"),)


class AnalysisDisease(models.Model):
    """생활습관 가이드 조회 기준 질환. ERD 복합 PK → id + unique"""

    id = fields.BigIntField(primary_key=True)
    analysis: fields.ForeignKeyRelation[Analysis] = fields.ForeignKeyField(
        "models.Analysis", related_name="diseases", on_delete=fields.CASCADE
    )
    # 칸 이름은 disease_id (값은 상병기호)
    disease: fields.ForeignKeyRelation["Disease"] = fields.ForeignKeyField(
        "models.Disease", related_name="analyses", to_field="code", on_delete=fields.RESTRICT
    )
    origin = fields.CharEnumField(enum_type=DiseaseOrigin, max_length=20)

    class Meta:
        table = "analysis_diseases"
        unique_together = (("analysis", "disease"),)


class AnalysisWarning(models.Model):
    """DB 조회로 결정적으로 산출한 경고. 0건이면 RG-02-E1"""

    id = fields.BigIntField(primary_key=True)
    analysis: fields.ForeignKeyRelation[Analysis] = fields.ForeignKeyField(
        "models.Analysis", related_name="warnings", on_delete=fields.CASCADE
    )
    warning_type = fields.CharField(max_length=30)
    severity = fields.CharField(max_length=10)
    item_a: fields.ForeignKeyNullableRelation["PrescriptionItem"] = fields.ForeignKeyField(
        "models.PrescriptionItem",
        related_name="warnings_a",
        null=True,
        source_field="item_id_a",
        on_delete=fields.SET_NULL,
    )
    item_b: fields.ForeignKeyNullableRelation["PrescriptionItem"] = fields.ForeignKeyField(
        "models.PrescriptionItem",
        related_name="warnings_b",
        null=True,
        source_field="item_id_b",
        on_delete=fields.SET_NULL,
    )
    reason = fields.TextField(null=True, description="DUR 금기 사유 원문")
    summary = fields.TextField(null=True, description="화면 표시 문장 (템플릿, AI 생성 아님 · NFR-032)")
    source = fields.CharField(max_length=100, null=True, description="고시명")
    notice_date = fields.DateField(null=True)
    daily_total = fields.DecimalField(
        max_digits=12, decimal_places=3, null=True, description="1일 최대용량 초과일 때만"
    )
    max_daily = fields.DecimalField(max_digits=12, decimal_places=3, null=True)
    detail: Any = fields.JSONField(
        null=True, description="(ERD 추가 제안) 약이 3개 이상인 경고의 전체 항목 번호 · 성분 · 근거 구분"
    )

    class Meta:
        table = "analysis_warnings"


class Guide(models.Model):
    """안내문 — 항목 고정 JSON (결과 일관성 NFR-030)"""

    id = fields.BigIntField(primary_key=True)
    analysis: fields.ForeignKeyRelation[Analysis] = fields.ForeignKeyField(
        "models.Analysis", related_name="guides", on_delete=fields.CASCADE
    )
    section = fields.CharEnumField(enum_type=GuideSection, max_length=30)
    status = fields.CharEnumField(enum_type=GuideStatus, max_length=20)
    content: Any = fields.JSONField(null=True)
    prompt_ver = fields.CharField(max_length=20, null=True)
    model_name = fields.CharField(max_length=50, null=True, description="AI 없이 만든 안내문은 null")
    tts_url = fields.CharField(max_length=500, null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "guides"
        unique_together = (("analysis", "section"),)
