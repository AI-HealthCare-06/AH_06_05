"""OCR 요청 · 응답 모양 — API 명세서 3장 (O-1 ~ O-5)"""

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import Field

from app.dtos.base import CamelModel


class JobCreatedResponse(CamelModel):
    job_id: int
    status: str


class FailedFile(CamelModel):
    file_index: int
    code: Literal["IMAGE_QUALITY_LOW", "NOT_A_DOCUMENT", "OCR_FAILED"]


class DuplicatedFile(CamelModel):
    """이미 올린 처방전이라 새로 저장하지 않은 사진 — 화면은 "이미 올린 처방전이에요"로 안내하고 prescription_id를 그대로 쓴다"""

    file_index: int
    prescription_id: int


class JobResponse(CamelModel):
    job_id: int
    status: Literal["queued", "running", "done", "failed"]
    prescription_ids: list[int]
    failed_files: list[FailedFile]
    duplicated_files: list[DuplicatedFile]  # 명세서에 추가 제안 (수인님 결정 10/14)


class CandidateResponse(CamelModel):
    edi_code: str | None
    item_seq: str | None
    item_name: str
    score: float | None


class ItemResponse(CamelModel):
    id: int
    raw_name: str
    item_name: str | None  # 약이 정해진 항목의 화면 표시 이름 (명세서 O-2에 추가 제안)
    match_status: str
    suggested_by: Literal["similar", "llm"] | None  # needs_confirm일 때 후보가 추천에서 왔는지 (명세서에 추가 제안)
    edi_code: str | None
    item_seq: str | None
    candidates: list[CandidateResponse]
    dose_per_time: float | None
    times_per_day: int | None
    total_days: int | None
    timing: str | None
    check_fields: list[str]  # 못 읽었거나 범위 밖이라 숫자를 다시 확인해야 하는 칸 (명세서에 추가 제안)
    guidance: list[
        str
    ]  # 약봉투에 약국이 인쇄한 복약 안내 표시 · 문장 (사진에서 읽은 글자 그대로, 명세서에 추가 제안). 없으면 빈 배열


class PrescriptionResponse(CamelModel):
    id: int
    doc_type: str
    issued_date: date | None
    hospital_name: str | None
    disease_codes: list[str]
    notices: list[
        str
    ]  # 사진을 읽을 때 사용자가 확인해야 할 점 (줄 수 불일치 · 칸 순서 추정 · 날짜 이상 등, 명세서에 추가 제안). 없으면 빈 배열
    items: list[ItemResponse]


class ItemPatchRequest(CamelModel):
    """O-3 — 보낸 칸만 바뀜. ediCode / itemSeq로 약 고르기, exclude로 빼기"""

    edi_code: str | None = Field(default=None, max_length=9)
    item_seq: str | None = Field(default=None, max_length=9)
    exclude: bool | None = None
    dose_per_time: Decimal | None = Field(default=None, gt=0, le=100, max_digits=10, decimal_places=3)
    times_per_day: int | None = Field(default=None, ge=1, le=24)
    total_days: int | None = Field(default=None, ge=1, le=365)


class DrugSearchItem(CamelModel):
    item_seq: str | None
    edi_code: str | None
    item_name: str
    entp_name: str | None
    etc_otc: str | None
    score: float


class DrugSearchResponse(CamelModel):
    status: Literal["matched", "candidates", "not_found"]
    items: list[DrugSearchItem]
