"""피처 1 OCR 서비스 — 업로드 검사 · OCR 작업 실행 · 인식 결과 조회 · 수정 · 약 이름 검색 (API O-1 ~ O-5)

OCR 작업은 FastAPI 백그라운드 작업으로 돌린다 (사진 원본은 메모리에만 두고 저장하지 않음 — NFR-011).
작업 안에서 사진 1장 = prescriptions 1행. 읽지 못한 사진은 ocr_jobs.error_code에 "Q2,D3,F1" 모양으로 적는다
(Q = IMAGE_QUALITY_LOW · D = NOT_A_DOCUMENT · F = OCR_FAILED, 숫자는 1부터 센 사진 번호).
"""

import asyncio
import hashlib
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from starlette import status
from tortoise.transactions import in_transaction

from app.core import config
from app.core.errors import AppError
from app.models.masters import Disease, DrugProduct
from app.models.ocr import (
    DocType,
    MatchStatus,
    OcrJob,
    OcrJobStatus,
    Prescription,
    PrescriptionDisease,
    PrescriptionItem,
    PrescriptionItemCandidate,
    QualityFlag,
)
from app.models.users import ConsentType, User, UserConsent
from app.services.drug_names import base_name
from app.services.ocr import clova, llm_fix, numeric, precheck
from app.services.ocr.mask import mask
from app.services.ocr.matcher import AMBIGUOUS, FOUND, NameMatcher
from app.services.ocr.pipeline import OcrRead, read

logger = logging.getLogger(__name__)

MAX_FILES = 5
MAX_BYTES = 10 * 1024 * 1024
FAIL_CODES = {"Q": "IMAGE_QUALITY_LOW", "D": "NOT_A_DOCUMENT", "F": "OCR_FAILED"}


# ── 마스터 캐시: 약제급여목록 · 상병마스터는 거의 안 바뀌어서 처음 쓸 때 한 번 읽는다 ──────────────
_matcher: NameMatcher | None = None
_codes: dict[str, str] | None = None
_lock = asyncio.Lock()


async def get_matcher() -> NameMatcher:
    global _matcher
    if _matcher is None:
        async with _lock:
            if _matcher is None:
                rows = await DrugProduct.all().values_list("edi_code", "item_name", "entp_name")
                _matcher = NameMatcher([(str(e), str(n)) for e, n, _ in rows], makers={str(m) for *_, m in rows if m})
    return _matcher


async def get_codes() -> dict[str, str]:
    global _codes
    if _codes is None:
        async with _lock:
            if _codes is None:
                rows = await Disease.all().values_list("code", "name_kr")
                _codes = {str(c): str(n) for c, n in rows}
    return _codes


def reset_caches() -> None:
    """마스터를 다시 넣은 뒤(스크립트 · 테스트) 호출"""
    global _matcher, _codes
    _matcher = None
    _codes = None


# ── O-1 업로드 검사 ───────────────────────────────────────────────────────────────────────────
@dataclass
class Blob:
    file_index: int  # 1부터
    content: bytes
    fmt: str  # jpg | png | pdf
    name: str


def detect_format(content: bytes) -> str | None:
    if content.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if content.startswith(b"%PDF"):
        return "pdf"
    return None


def validate_uploads(raw: list[tuple[str, bytes]]) -> list[Blob]:
    """raw: [(파일 이름, 내용)] → 문제가 있으면 400 (detail.fileIndex)"""
    if not raw:
        raise AppError(status.HTTP_400_BAD_REQUEST, "VALIDATION_ERROR", "사진을 한 장 이상 올려 주세요.", field="files")
    if len(raw) > MAX_FILES:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            "TOO_MANY_FILES",
            f"사진은 한 번에 {MAX_FILES}장까지 올릴 수 있어요.",
            field="files",
        )
    blobs = []
    for i, (_name, content) in enumerate(raw, start=1):
        if len(content) > MAX_BYTES:
            raise AppError(
                status.HTTP_400_BAD_REQUEST,
                "FILE_TOO_LARGE",
                f"{i}번째 사진이 너무 커요. 10MB 이하로 올려 주세요.",
                field="files",
                detail={"fileIndex": i},
            )
        fmt = detect_format(content)
        if fmt is None:
            raise AppError(
                status.HTTP_400_BAD_REQUEST,
                "FILE_TYPE_NOT_SUPPORTED",
                f"{i}번째 파일은 올릴 수 없어요. 사진(JPG, PNG)이나 PDF만 올려 주세요.",
                field="files",
                detail={"fileIndex": i},
            )
        blobs.append(Blob(i, content, fmt, f"photo{i}"))
    return blobs


async def has_health_consent(user: User) -> bool:
    return await UserConsent.filter(
        user=user, consent_type=ConsentType.SENSITIVE_HEALTH, agreed=True, withdrawn_at=None
    ).exists()


async def create_job(user: User, blobs: list[Blob]) -> OcrJob:
    if not await has_health_consent(user):
        raise AppError(
            status.HTTP_403_FORBIDDEN, "CONSENT_REQUIRED", "건강 정보 사용에 동의해야 처방전을 올릴 수 있어요."
        )
    return await OcrJob.create(user=user, status=OcrJobStatus.QUEUED, file_count=len(blobs))


# ── OCR 작업 실행 ─────────────────────────────────────────────────────────────────────────────
def _failure_code(data: dict[str, Any], res: OcrRead) -> str:
    """읽지 못한 사진을 Q(흐림 · 기울음 · 표 일부 잘림) 또는 D(문서가 아닌 듯)로 나눔"""
    if res.reason == "tilt":
        return "Q"
    fields = data.get("images", [{}])[0].get("fields", [])
    confs = [f.get("inferConfidence", 0) for f in fields]
    if len(fields) < 12 or (confs and sum(confs) / len(confs) < 0.8):
        return "Q"
    return "D"


def _clamp(score: float) -> Decimal:
    return Decimal(str(round(min(max(score, 0.0), 1.0), 4)))


async def save_read(user_id: int, job_id: int, file_index: int, res: OcrRead, key: str | None = None) -> int:
    """읽은 결과를 prescriptions · 질병 · 약 · 후보로 저장하고 처방전 ID를 돌려줌"""
    async with in_transaction():
        rx = await Prescription.create(
            user_id=user_id,
            ocr_job_id=job_id,
            file_index=file_index,
            doc_type=DocType.PRESCRIPTION,
            issued_date=res.issued,
            hospital_name=res.hospital_name,
            ocr_raw_text=mask(res.raw_text),  # 이름 · 주민번호 · 전화번호 등을 가린 뒤 저장 (수인님 결정 10/14)
            content_key=key,
            ocr_confidence=Decimal(str(res.confidence)) if res.confidence is not None else None,
            quality_flag=QualityFlag.OK,
        )
        # 상병마스터에 있고 글자 확실도도 높은 코드만 바로 쓴다. 나머지(보정 · 후보 여러 개 · 모름)는 비워 두고
        # 사용자가 고르게 한다 (RG-05-E1) — 잘못된 질환으로 생활습관 안내가 나가는 것을 막기 위해
        seen: set[str] = set()
        for d in res.diseases:
            if d.confirmed and isinstance(d.value, str) and d.value not in seen:
                seen.add(d.value)
                await PrescriptionDisease.create(prescription=rx, disease_id=d.value, is_main=len(seen) == 1)
        for r in res.rows:
            dec = r.decision
            item_kwargs: dict[str, Any] = {
                "prescription": rx,
                "raw_name": r.read_name[:300],
                "dose_per_time": Decimal(str(r.dose)) if r.dose is not None else None,
                "times_per_day": int(r.times) if r.times is not None else None,
                "total_days": int(r.days) if r.days is not None else None,
                "timing": res.timing,
            }
            if dec.status == FOUND:
                best = dec.candidates[0]
                item = await PrescriptionItem.create(
                    **item_kwargs, drug_id=best.edi_code, match_score=_clamp(best.score), match_status=MatchStatus.AUTO
                )
            elif dec.status == AMBIGUOUS:
                item = await PrescriptionItem.create(
                    **item_kwargs, match_score=_clamp(dec.score), match_status=MatchStatus.NEEDS_CONFIRM
                )
            else:
                item = await PrescriptionItem.create(
                    **item_kwargs, match_score=_clamp(dec.score), match_status=MatchStatus.UNMATCHED
                )
            if dec.status in (FOUND, AMBIGUOUS):
                for rank, c in enumerate(dec.candidates, start=1):
                    await PrescriptionItemCandidate.create(
                        item=item, rank=rank, drug_id=c.edi_code, score=_clamp(c.score)
                    )
    return rx.id


def _line_key(ident: str | None, dose: Any, times: Any, days: Any) -> tuple[Any, ...]:
    """약 1줄의 열쇠. 숫자는 float · int로 맞춰 읽은 직후(소수 · 정수)와 DB(Decimal)에서 같은 값이 되게 한다.
    확정 못 한 약 이름은 띄어쓰기를 지우고 저장 길이(300자)로 자른다 (같은 처방전을 읽을 때 띄어쓰기만 달라지는 경우가 있음)"""
    return (
        ident,
        None if dose is None else float(dose),
        None if times is None else int(times),
        None if days is None else int(days),
    )


def _name_key(name: str) -> str:
    return re.sub(r"\s+", "", name)[:300]


def make_key(issued: Any, hospital: str | None, lines: list[tuple[Any, ...]]) -> str | None:
    """같은 처방전을 두 번 올렸는지 보는 열쇠 — 병원 · 교부일 · 약 목록(약 번호 또는 읽은 이름 + 복용 숫자)이 모두 같을 때만 같다고 본다.
    이미지끼리 비교하면 숫자 한 글자만 다른 처방전도 같게 나와서(실험), 읽은 내용으로 비교한다. 정보가 모자라면 None(비교하지 않음)"""
    if not (issued and hospital and lines):
        return None
    raw = json.dumps([str(issued), hospital, lines], ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def content_key(res: OcrRead) -> str | None:
    """읽은 직후의 열쇠"""
    lines = [
        _line_key(
            r.decision.candidates[0].edi_code if r.decision.status == FOUND else _name_key(r.read_name),
            r.dose,
            r.times,
            r.days,
        )
        for r in res.rows
    ]
    return make_key(res.issued, res.hospital_name, lines)


async def saved_content_key(rx: Prescription) -> str | None:
    """이미 저장된 처방전의 열쇠 (content_key를 도입하기 전에 저장한 기록용). 자동으로 확정된 줄은 약 번호,
    나머지는 읽은 이름 — 읽은 직후와 같은 규칙. 사용자가 약을 바꿨다면 달라질 수 있다 (그때는 못 찾을 뿐 잘못 합치지는 않음)"""
    items = await PrescriptionItem.filter(prescription_id=rx.id).order_by("id")
    lines = [
        _line_key(
            it.drug_id  # type: ignore[attr-defined]
            if it.match_status == MatchStatus.AUTO and it.drug_id  # type: ignore[attr-defined]
            else _name_key(it.raw_name),
            it.dose_per_time,
            it.times_per_day,
            it.total_days,
        )
        for it in items
    ]
    return make_key(rx.issued_date, rx.hospital_name, lines)


async def run_job(job_id: int, user_id: int, blobs: list[Blob]) -> None:
    """백그라운드 작업. 어떤 오류가 나도 작업이 queued · running에 멈춰 있지 않게 마무리한다"""
    try:
        await OcrJob.filter(id=job_id).update(status=OcrJobStatus.RUNNING)
        matcher, codes = await get_matcher(), await get_codes()
        failures: list[str] = []
        saved = 0
        # OCR(유료 호출)을 부르기 전에 너무 작은 · 흐린 사진, 똑같은 사진을 거름 (이미지를 여는 계산이라 별도 스레드에서)
        screened = await asyncio.to_thread(precheck.screen, blobs)
        failures += [f"Q{i}" for i in sorted([*screened.too_small, *screened.blurry])]
        saved_ids: dict[int, int] = {}  # 사진 번호 → 처방전 ID (새로 저장했거나 이미 있던 것)
        duplicated: list[dict[str, int]] = []
        for b in screened.ready:
            try:
                data = await clova.recognize(b.content, b.fmt, b.name)
                res = read(data, matcher, codes)
            except clova.ClovaError as e:
                logger.warning("CLOVA OCR 실패 job=%s file=%s (%s)", job_id, b.file_index, e)
                failures.append(f"F{b.file_index}")
                continue
            if res.status != "ok":
                failures.append(f"{_failure_code(data, res)}{b.file_index}")
                continue
            # 규칙이 못 찾은 약 이름만 LLM이 고쳐 "추천" (꺼짐이 기본 · 실패해도 규칙 결과 그대로)
            res = await llm_fix.apply(res, matcher)
            key = content_key(res)
            # 병원 · 교부일 · 약 목록이 모두 같은 처방전이 이미 있으면(이 작업의 앞 사진이든 지난번 업로드든) 새로 저장하지 않고
            # 기존 기록을 쓰게 한다 (수인님 결정 10/14: "이미 올린 처방전이에요"로 안내 + 기존 기록 사용)
            existing = (
                await Prescription.filter(user_id=user_id, content_key=key).order_by("id").first() if key else None
            )
            if existing is not None:
                logger.info(
                    "이미 있는 처방전이라 저장하지 않음 job=%s file=%s rx=%s", job_id, b.file_index, existing.id
                )
                saved_ids[b.file_index] = existing.id
                duplicated.append({"fileIndex": b.file_index, "prescriptionId": existing.id})
                continue
            saved_ids[b.file_index] = await save_read(user_id, job_id, b.file_index, res, key)
            saved += 1
        for i, first in screened.duplicates.items():  # 바이트가 똑같은 사진은 먼저 읽은 사진의 처방전을 가리킴
            logger.info("같은 사진이라 건너뜀 job=%s file=%s (=%s번)", job_id, i, first)
            if first in saved_ids:
                duplicated.append({"fileIndex": i, "prescriptionId": saved_ids[first]})
        duplicated.sort(key=lambda d: d["fileIndex"])
        all_failed_service = saved == 0 and failures and all(f.startswith("F") for f in failures)
        await OcrJob.filter(id=job_id).update(
            status=OcrJobStatus.FAILED if all_failed_service else OcrJobStatus.DONE,
            error_code=",".join(failures)[:50] or None,
            duplicates=duplicated or None,
            finished_at=datetime.now(config.TIMEZONE),
        )
    except Exception:
        logger.exception("OCR 작업 실패 job=%s", job_id)
        await OcrJob.filter(id=job_id).update(
            status=OcrJobStatus.FAILED, error_code="OCR_FAILED", finished_at=datetime.now(config.TIMEZONE)
        )
    finally:
        # 사진 원본은 저장하지 않는다 (참조를 끊어 메모리에서 버림)
        for b in blobs:
            b.content = b""


# ── O-5 · O-2 · O-3 · O-4 ────────────────────────────────────────────────────────────────────
async def get_job(user: User, job_id: int) -> dict[str, Any]:
    job = await OcrJob.get_or_none(id=job_id, user=user)
    if job is None:
        raise AppError(status.HTTP_404_NOT_FOUND, "NOT_FOUND")
    # 이 작업에서 새로 저장한 처방전 + 이미 있어서 새로 저장하지 않은 사진이 가리키는 기존 처방전을 사진 순서대로
    pairs = await Prescription.filter(ocr_job_id=job.id).values_list("file_index", "id")
    dups = [(d["fileIndex"], d["prescriptionId"]) for d in (job.duplicates or [])]
    ids = list(dict.fromkeys(i for _, i in sorted([*pairs, *dups], key=lambda p: (p[0] or 0, p[1]))))
    failed = []
    for token in (job.error_code or "").split(","):
        if token[:1] in FAIL_CODES and token[1:].isdigit():
            failed.append({"fileIndex": int(token[1:]), "code": FAIL_CODES[token[0]]})
    return {
        "jobId": job.id,
        "status": job.status.value,
        "prescriptionIds": ids,
        "failedFiles": failed,
        "duplicatedFiles": [{"fileIndex": f, "prescriptionId": i} for f, i in dups],
    }


def item_display_name(drug: DrugProduct | None) -> str | None:
    return base_name(drug.item_name) if drug else None


def check_fields(item: PrescriptionItem) -> list[str]:
    missing = [
        label
        for label, v in (("1회량", item.dose_per_time), ("하루 횟수", item.times_per_day), ("총 일수", item.total_days))
        if v is None
    ]
    dose = float(item.dose_per_time) if item.dose_per_time is not None else None
    return missing + numeric.check(dose, item.times_per_day, item.total_days)


async def get_prescription(user: User, prescription_id: int) -> dict[str, Any]:
    rx = await Prescription.get_or_none(id=prescription_id, user=user)
    if rx is None:
        raise AppError(status.HTTP_404_NOT_FOUND, "NOT_FOUND")
    diseases = (
        await PrescriptionDisease.filter(prescription=rx)
        .order_by("-is_main", "id")
        .values_list("disease_id", flat=True)
    )
    items = await PrescriptionItem.filter(prescription=rx).order_by("id").prefetch_related("drug")
    cands = await PrescriptionItemCandidate.filter(item__prescription=rx).order_by("rank").prefetch_related("drug")
    by_item: dict[int, list[PrescriptionItemCandidate]] = {}
    for c in cands:
        by_item.setdefault(c.item_id, []).append(c)  # type: ignore[attr-defined]
    out_items = []
    for it in items:
        confirmed = it.match_status in (MatchStatus.AUTO, MatchStatus.USER_CONFIRMED)
        out_items.append(
            {
                "id": it.id,
                "rawName": it.raw_name,
                "itemName": item_display_name(it.drug) if confirmed else None,
                "matchStatus": it.match_status.value,
                "ediCode": it.drug.edi_code if it.drug else None,
                "itemSeq": it.drug.item_seq if it.drug else None,
                "candidates": [
                    {
                        "ediCode": c.drug.edi_code,
                        "itemSeq": c.drug.item_seq,
                        "itemName": base_name(c.drug.item_name),
                        "score": float(c.score) if c.score is not None else None,
                    }
                    for c in by_item.get(it.id, [])
                ]
                if it.match_status == MatchStatus.NEEDS_CONFIRM
                else [],
                "dosePerTime": float(it.dose_per_time) if it.dose_per_time is not None else None,
                "timesPerDay": it.times_per_day,
                "totalDays": it.total_days,
                "timing": it.timing,
                "checkFields": check_fields(it) if it.match_status != MatchStatus.EXCLUDED else [],
            }
        )
    return {
        "id": rx.id,
        "docType": rx.doc_type.value,
        "issuedDate": rx.issued_date,
        "hospitalName": rx.hospital_name,
        "diseaseCodes": list(diseases),
        "items": out_items,
    }


async def patch_item(user: User, prescription_id: int, item_id: int, body: Any) -> None:
    """O-3 — 보낸 칸만 바꿈 (body: ItemPatchRequest)"""
    item = await PrescriptionItem.get_or_none(id=item_id, prescription_id=prescription_id, prescription__user=user)
    if item is None:
        raise AppError(status.HTTP_404_NOT_FOUND, "NOT_FOUND")
    sent = body.model_fields_set
    if body.exclude:
        item.drug_id = None  # type: ignore[attr-defined]
        item.match_status = MatchStatus.EXCLUDED
    elif "edi_code" in sent or "item_seq" in sent:
        drug = None
        if body.edi_code:
            drug = await DrugProduct.get_or_none(edi_code=body.edi_code)
        elif body.item_seq:
            drug = await DrugProduct.filter(item_seq=body.item_seq).first()
        if drug is None:
            raise AppError(
                status.HTTP_400_BAD_REQUEST,
                "VALIDATION_ERROR",
                "고른 약을 찾을 수 없어요. 다시 골라 주세요.",
                field="ediCode" if body.edi_code or not body.item_seq else "itemSeq",
            )
        item.drug_id = drug.edi_code  # type: ignore[attr-defined]
        item.match_status = MatchStatus.USER_CONFIRMED
    if "dose_per_time" in sent:
        item.dose_per_time = body.dose_per_time
    if "times_per_day" in sent:
        item.times_per_day = body.times_per_day
    if "total_days" in sent:
        item.total_days = body.total_days
    await item.save()


async def search_drugs(q: str, size: int) -> dict[str, Any]:
    """O-4 — 이름 맞추기는 OCR과 같은 함수(NameMatcher). 정확히 같을 때만 matched"""
    matcher = await get_matcher()
    dec = matcher.decide(q, top_n=max(size, 3))  # 비슷한 약이 여럿인지 보려면 최소 3개는 봐야 함
    if dec.status not in (FOUND, AMBIGUOUS):
        return {"status": "not_found", "items": []}
    drugs = {d.edi_code: d for d in await DrugProduct.filter(edi_code__in=[c.edi_code for c in dec.candidates])}
    items = []
    for c in dec.candidates:
        d = drugs.get(c.edi_code)
        if d is None:
            continue
        items.append(
            {
                "itemSeq": d.item_seq,
                "ediCode": d.edi_code,
                "itemName": base_name(d.item_name),
                "entpName": d.entp_name,
                "etcOtc": d.etc_otc,
                "score": float(_clamp(c.score)),
            }
        )
    exact = dec.status == FOUND and dec.same_name
    return {"status": "matched" if exact else "candidates", "items": items[:1] if exact else items[:size]}
