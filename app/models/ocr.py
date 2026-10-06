"""피처 1 OCR — 처방전 · 약봉투 입력 (ERD v1.3 입력 영역, API O-1 ~ O-5)

원본 사진은 저장하지 않는다 (NFR-011). 사진 1장 = prescriptions 1행.
"""

from enum import StrEnum
from typing import TYPE_CHECKING

from tortoise import fields, models

if TYPE_CHECKING:
    from app.models.masters import Disease, DrugProduct
    from app.models.users import User


class OcrJobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class DocType(StrEnum):
    PRESCRIPTION = "prescription"  # 처방전
    PILL_BAG = "pill_bag"  # 약봉투 — 질병코드 없음 → RG-05-E1


class QualityFlag(StrEnum):
    OK = "ok"
    LOW = "low"  # OC-01-E1에서 "그래도 계속 진행"


class MatchStatus(StrEnum):
    AUTO = "auto"  # 약 코드 또는 제품명 + 함량이 정확히 일치
    NEEDS_CONFIRM = "needs_confirm"  # 사용자 확인 필요 (분석 시작 불가, REQ-033)
    USER_CONFIRMED = "user_confirmed"
    UNMATCHED = "unmatched"
    EXCLUDED = "excluded"  # 빼고 진행


class OcrJob(models.Model):
    """O-1 업로드 = 작업 1개 (사진 최대 5장). O-5로 상태 조회"""

    id = fields.BigIntField(primary_key=True)
    user: fields.ForeignKeyRelation["User"] = fields.ForeignKeyField(
        "models.User", related_name="ocr_jobs", on_delete=fields.CASCADE
    )
    status = fields.CharEnumField(enum_type=OcrJobStatus, max_length=20, default=OcrJobStatus.QUEUED)
    file_count = fields.SmallIntField(description="한 번에 올린 사진 수 (최대 5)")
    error_code = fields.CharField(max_length=50, null=True, description="전체 실패 시 OCR_FAILED 등")
    created_at = fields.DatetimeField(auto_now_add=True)
    finished_at = fields.DatetimeField(null=True)

    class Meta:
        table = "ocr_jobs"


class Prescription(models.Model):
    id = fields.BigIntField(primary_key=True)
    user: fields.ForeignKeyRelation["User"] = fields.ForeignKeyField(
        "models.User", related_name="prescriptions", on_delete=fields.CASCADE
    )
    ocr_job: fields.ForeignKeyNullableRelation[OcrJob] = fields.ForeignKeyField(
        "models.OcrJob", related_name="prescriptions", null=True, on_delete=fields.SET_NULL
    )
    file_index = fields.SmallIntField(null=True, description="작업 안에서 몇 번째 사진인지")
    doc_type = fields.CharEnumField(enum_type=DocType, max_length=20)
    issued_date = fields.DateField(null=True, description="처방 교부일")
    hospital_name = fields.CharField(max_length=200, null=True)
    ocr_raw_text = fields.TextField(null=True, description="OCR 원문 — 암호화 저장 예정 (원본 이미지는 저장 안 함)")
    ocr_confidence = fields.DecimalField(max_digits=5, decimal_places=4, null=True)
    quality_flag = fields.CharEnumField(enum_type=QualityFlag, max_length=20, null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "prescriptions"


class PrescriptionDisease(models.Model):
    """처방전 질병분류기호 (주상병 + 부상병 여러 개). ERD 복합 PK → id + unique"""

    id = fields.BigIntField(primary_key=True)
    prescription: fields.ForeignKeyRelation["Prescription"] = fields.ForeignKeyField(
        "models.Prescription", related_name="diseases", on_delete=fields.CASCADE
    )
    # 칸 이름은 disease_id (값은 상병기호). source_field로 바꾸면 unique_together가 깨짐 (Tortoise 0.25)
    disease: fields.ForeignKeyRelation["Disease"] = fields.ForeignKeyField(
        "models.Disease", related_name="prescriptions", to_field="code", on_delete=fields.RESTRICT
    )
    is_main = fields.BooleanField(default=False, description="주상병 여부")

    class Meta:
        table = "prescription_diseases"
        unique_together = (("prescription", "disease"),)


class PrescriptionItem(models.Model):
    """처방 약 1줄. needs_confirm · unmatched가 남으면 분석 시작 불가 (REQ-033)"""

    id = fields.BigIntField(primary_key=True)
    prescription: fields.ForeignKeyRelation["Prescription"] = fields.ForeignKeyField(
        "models.Prescription", related_name="items", on_delete=fields.CASCADE
    )
    drug: fields.ForeignKeyNullableRelation["DrugProduct"] = fields.ForeignKeyField(
        "models.DrugProduct",
        related_name="prescription_items",
        to_field="edi_code",
        null=True,
        source_field="edi_code",
        on_delete=fields.RESTRICT,
        description="매칭 실패 · 제외 시 null",
    )
    raw_name = fields.CharField(max_length=300, description="OCR이 읽은 원문 약품명")
    match_score = fields.DecimalField(max_digits=5, decimal_places=4, null=True)
    match_status = fields.CharEnumField(enum_type=MatchStatus, max_length=20)
    dose_per_time = fields.DecimalField(max_digits=10, decimal_places=3, null=True)
    times_per_day = fields.SmallIntField(null=True)
    total_days = fields.SmallIntField(null=True)
    timing = fields.CharField(max_length=50, null=True, description="아침 식후 등")

    class Meta:
        table = "prescription_items"


class PrescriptionItemCandidate(models.Model):
    """OC-02 후보 목록 (1순위 적중률 · 5순위 내 포함률 측정용). ERD 복합 PK → id + unique"""

    id = fields.BigIntField(primary_key=True)
    item: fields.ForeignKeyRelation["PrescriptionItem"] = fields.ForeignKeyField(
        "models.PrescriptionItem", related_name="candidates", on_delete=fields.CASCADE
    )
    rank = fields.SmallIntField()
    drug: fields.ForeignKeyRelation["DrugProduct"] = fields.ForeignKeyField(
        "models.DrugProduct",
        related_name="candidate_items",
        to_field="edi_code",
        source_field="edi_code",
        on_delete=fields.RESTRICT,
    )
    score = fields.DecimalField(max_digits=5, decimal_places=4, null=True)

    class Meta:
        table = "prescription_item_candidates"
        unique_together = (("item", "rank"),)
