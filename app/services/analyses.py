# mypy: disable-error-code=union-attr
"""피처 2 RAG 분석 서비스 (API R-1 ~ R-9)

분석 한 번 = ① 약 정보 확인 → ② 안전성 점검(DB 조회만, AI 없음) → ③ 안내문 작성(정해진 자료로만, AI 없음) 순서로
FastAPI 백그라운드 작업에서 돌린다. 단계마다 current_step을 갱신해 R-2가 진행 상태를 보여 주고,
실패하면 failed_step에 적어 두어 R-3 다시 시도가 그 단계부터 이어서 한다.
"""

import asyncio
import base64
import json
import logging
from collections import Counter
from datetime import date, datetime, timedelta
from typing import Any

from starlette import status
from tortoise.transactions import in_transaction

from app.core import config
from app.core.errors import AppError
from app.models.analysis import (
    Analysis,
    AnalysisDisease,
    AnalysisPrescription,
    AnalysisStatus,
    AnalysisStep,
    AnalysisWarning,
    DiseaseOrigin,
    Guide,
    GuideFeedback,
    GuideSection,
    GuideStatus,
)
from app.models.masters import Disease
from app.models.ocr import MatchStatus, Prescription, PrescriptionDisease, PrescriptionItem
from app.models.users import User
from app.services import safety
from app.services.drug_names import base_name
from app.services.guide import lifestyle, medication, store
from app.services.prescriptions import has_health_consent

logger = logging.getLogger(__name__)

MAX_PRESCRIPTIONS = 5
MAX_RETRIES = 3
TIMEOUT_SECONDS = 60
ESTIMATED_SECONDS = 20
STEPS = [AnalysisStep.DRUG_INFO, AnalysisStep.SAFETY_CHECK, AnalysisStep.GUIDE_GENERATION]
STEP_LABELS = {
    AnalysisStep.DRUG_INFO: "약 정보 확인",
    AnalysisStep.SAFETY_CHECK: "같이 먹으면 안 되는 약 점검",
    AnalysisStep.GUIDE_GENERATION: "안내문 작성",
}
ERROR_MESSAGES = {
    "SAFETY_CHECK_FAILED": "안전성 점검을 하지 못했어요.",
    "GUIDE_GENERATION_FAILED": "안내문을 만들지 못했어요.",
    "TIMEOUT": "시간이 너무 오래 걸렸어요.",
}
TITLES = {
    "interaction": "함께 먹으면 안 되는 약",
    "duplicate_ingredient": "같은 성분이 겹쳐요",
    "duplicate_efficacy": "효과가 비슷한 약이 겹쳐요",
    "elderly": "어르신이 조심해야 하는 약",
    "age": "나이에 맞지 않는 약",
    "dose_exceed": "하루 최대량을 넘어요",
    "polypharmacy": "여러 약을 함께 먹고 있어요",
}
CHECKED_ITEMS = [
    ("interaction", "함께 먹으면 안 되는 약"),
    ("duplicate", "같은 성분 · 같은 효과 중복"),
    ("elderly_age", "어르신 주의 · 나이 금기"),
    ("dose_exceed", "하루 최대량 초과"),
    ("polypharmacy", "여러 약 함께 복용"),
]
ACTION_ADVICE = {
    "interaction": "약을 임의로 끊지 말고, 처방한 의사나 약사와 먼저 상의하세요.",
    "polypharmacy": "먹는 약을 한꺼번에 정리해서 약사와 한 번 상의해 보세요.",
}
DEFAULT_ADVICE = "약을 임의로 끊거나 바꾸지 말고, 처방한 의사나 약사와 먼저 상의하세요."
DISCLAIMER = "의학적 진단 · 처방이 아닌 참고용 안내예요"
SEVERITY_ORDER = {"danger": 0, "caution": 1, "info": 2}
USABLE = (MatchStatus.AUTO, MatchStatus.USER_CONFIRMED)


def _now() -> datetime:
    return datetime.now(config.TIMEZONE)


async def _get(user: User, analysis_id: int) -> Analysis:
    a = await Analysis.get_or_none(id=analysis_id, user=user)
    if a is None:
        raise AppError(status.HTTP_404_NOT_FOUND, "NOT_FOUND")
    return a


async def _items(analysis: Analysis) -> list[PrescriptionItem]:
    """분석에 쓴 처방전의 약 전체 (약 · 처방전 불러옴, 처방 순서)"""
    rx_ids = await AnalysisPrescription.filter(analysis=analysis).values_list("prescription_id", flat=True)
    return (
        await PrescriptionItem.filter(prescription_id__in=list(rx_ids))
        .order_by("prescription_id", "id")
        .prefetch_related("drug", "prescription")
    )


# ── R-1 분석 시작 ─────────────────────────────────────────────────────────────────────────────
async def create_analysis(user: User, prescription_ids: list[int]) -> Analysis:
    ids = list(dict.fromkeys(prescription_ids))
    if not await has_health_consent(user):
        raise AppError(status.HTTP_403_FORBIDDEN, "CONSENT_REQUIRED", "건강 정보 사용에 동의해야 분석할 수 있어요.")
    rx_list = await Prescription.filter(id__in=ids, user=user)
    if len(rx_list) != len(ids):
        raise AppError(status.HTTP_404_NOT_FOUND, "NOT_FOUND")
    items = await PrescriptionItem.filter(prescription_id__in=ids)
    if any(i.match_status in (MatchStatus.NEEDS_CONFIRM, MatchStatus.UNMATCHED) for i in items):
        raise AppError(
            status.HTTP_409_CONFLICT,
            "ITEMS_NOT_CONFIRMED",
            "아직 확인하지 않은 약이 있어요. 약을 고르거나 빼 주세요.",
        )
    if not any(i.match_status in USABLE for i in items):
        raise AppError(
            status.HTTP_409_CONFLICT, "ITEMS_NOT_CONFIRMED", "점검할 약이 없어요. 약을 한 개 이상 확인해 주세요."
        )
    async with in_transaction():
        analysis = await Analysis.create(user=user, user_birth_year=user.birth_year)
        for rx in rx_list:
            await AnalysisPrescription.create(analysis=analysis, prescription=rx)
        codes = (
            await PrescriptionDisease.filter(prescription_id__in=ids)
            .order_by("-is_main", "id")
            .values_list("disease_id", flat=True)
        )
        for code in dict.fromkeys(codes):
            await AnalysisDisease.create(analysis=analysis, disease_id=code, origin=DiseaseOrigin.PRESCRIPTION)
    return analysis


# ── 백그라운드 실행 ───────────────────────────────────────────────────────────────────────────
async def _set_step(analysis_id: int, step: AnalysisStep) -> bool:
    """단계 시작 표시. 이미 실패(시간 초과 등)로 닫힌 분석이면 False"""
    n = await Analysis.filter(id=analysis_id, status__in=[AnalysisStatus.QUEUED, AnalysisStatus.RUNNING]).update(
        status=AnalysisStatus.RUNNING, current_step=step, started_at=_now()
    )
    return bool(n)


async def _fail(analysis_id: int, step: AnalysisStep, code: str) -> None:
    await Analysis.filter(id=analysis_id, status__in=[AnalysisStatus.QUEUED, AnalysisStatus.RUNNING]).update(
        status=AnalysisStatus.FAILED, failed_step=step, error_code=code, finished_at=_now()
    )


def _to_checker_items(items: list[PrescriptionItem]) -> list[safety.checker.Item]:
    return [
        safety.checker.Item(
            item_id=str(i.id),
            edi_code=i.drug.edi_code,
            prescription_id=str(i.prescription_id),  # type: ignore[attr-defined]
            issued_date=i.prescription.issued_date,
            total_days=i.total_days,
            dose_per_time=float(i.dose_per_time) if i.dose_per_time is not None else None,
            times_per_day=i.times_per_day,
            hospital=i.prescription.hospital_name,
        )
        for i in items
    ]


def _run_check(items: list[safety.checker.Item], birth_year: int, sex: str | None) -> safety.checker.CheckResult:
    checker = safety.get_checker()
    with safety.check_lock():
        return checker.check(items, safety.checker.Patient(birth_year=birth_year, sex=sex))


def _parse_date(value: str | None) -> date | None:
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


async def _safety_step(analysis: Analysis, items: list[PrescriptionItem], user: User) -> None:
    result = await asyncio.to_thread(
        _run_check,
        _to_checker_items(items),
        analysis.user_birth_year or user.birth_year,
        user.sex.value if user.sex else None,
    )
    async with in_transaction():
        await AnalysisWarning.filter(analysis=analysis).delete()
        for w in result.warnings:
            ids = [int(x) for x in w.item_ids]
            d = w.detail or {}
            await AnalysisWarning.create(
                analysis=analysis,
                warning_type=w.warning_type,
                severity=w.severity,
                item_a_id=ids[0] if ids else None,
                item_b_id=ids[1] if len(ids) > 1 else None,
                reason=w.reason,
                summary=w.summary,
                source=w.source,
                notice_date=_parse_date(w.notice_date),
                daily_total=d.get("daily_total"),
                max_daily=d.get("daily_max"),
                detail={"itemIds": ids, **{k: v for k, v in d.items() if k != "drugs"}},
            )


async def _guide_step(analysis: Analysis, items: list[PrescriptionItem]) -> None:
    usable = [i for i in items if i.match_status in USABLE and i.drug]
    codes = [
        str(c)
        for c in await AnalysisDisease.filter(analysis=analysis).order_by("id").values_list("disease_id", flat=True)
    ]
    med = medication.build(usable, await store.lookup([i.drug.edi_code for i in usable]))
    life = lifestyle.build(codes, usable)
    async with in_transaction():
        await Guide.filter(analysis=analysis).delete()
        await Guide.create(analysis=analysis, section=GuideSection.MEDICATION, status=GuideStatus.DONE, content=med)
        await Guide.create(analysis=analysis, section=GuideSection.LIFESTYLE, status=GuideStatus.DONE, content=life)


async def run_analysis(analysis_id: int, from_step: AnalysisStep = AnalysisStep.DRUG_INFO) -> None:
    """어떤 오류가 나도 분석이 queued · running에 멈춰 있지 않게 마무리한다"""
    step = from_step
    try:
        analysis = await Analysis.get(id=analysis_id)
        user = await User.get(id=analysis.user_id)  # type: ignore[attr-defined]
        for step in STEPS[STEPS.index(from_step) :]:
            if not await _set_step(analysis_id, step):
                return
            items = await _items(analysis)
            if step == AnalysisStep.DRUG_INFO:
                continue  # 약 정보는 이미 처방 확인 단계에서 맞춰져 있음 — 불러온 약이 점검 대상
            if step == AnalysisStep.SAFETY_CHECK:
                usable = [i for i in items if i.match_status in USABLE and i.drug]
                await _safety_step(analysis, usable, user)
            else:
                await _guide_step(analysis, items)
        await Analysis.filter(id=analysis_id, status=AnalysisStatus.RUNNING).update(
            status=AnalysisStatus.DONE, current_step=None, finished_at=_now()
        )
    except Exception:
        logger.exception("분석 실패 analysis=%s step=%s", analysis_id, step)
        code = "SAFETY_CHECK_FAILED" if step != AnalysisStep.GUIDE_GENERATION else "GUIDE_GENERATION_FAILED"
        await _fail(analysis_id, step, code)


# ── R-2 진행 상태 · R-3 다시 시도 ──────────────────────────────────────────────────────────────
async def _expire_if_stuck(a: Analysis) -> Analysis:
    """60초 넘게 끝나지 않으면 TIMEOUT으로 닫음 (RG-01-E1)"""
    if a.status in (AnalysisStatus.QUEUED, AnalysisStatus.RUNNING):
        since = a.started_at or a.created_at
        if _now() - since > timedelta(seconds=TIMEOUT_SECONDS):
            await _fail(a.id, a.current_step or AnalysisStep.DRUG_INFO, "TIMEOUT")
            return await Analysis.get(id=a.id)
    return a


def _step_states(a: Analysis) -> list[dict[str, str]]:
    cur = a.failed_step if a.status == AnalysisStatus.FAILED else a.current_step
    out = []
    for s in STEPS:
        if a.status == AnalysisStatus.DONE:
            state = "done"
        elif cur is None:
            state = "pending"
        elif STEPS.index(s) < STEPS.index(cur):
            state = "done"
        elif s == cur:
            state = "failed" if a.status == AnalysisStatus.FAILED else "running"
        else:
            state = "pending"
        out.append({"key": s.value, "label": STEP_LABELS[s], "state": state})
    return out


async def _counts(a: Analysis) -> tuple[int, int]:
    items = await _items(a)
    usable = sum(1 for i in items if i.match_status in USABLE and i.drug)
    return usable, len(items) - usable


async def get_status(user: User, analysis_id: int) -> dict[str, Any]:
    a = await _expire_if_stuck(await _get(user, analysis_id))
    out: dict[str, Any] = {"analysisId": a.id, "status": a.status.value, "steps": _step_states(a)}
    if a.status == AnalysisStatus.FAILED:
        code = a.error_code or "GUIDE_GENERATION_FAILED"
        out["error"] = {"code": code, "message": ERROR_MESSAGES.get(code, "분석을 마치지 못했어요.")}
        out["partialResultAvailable"] = bool(a.failed_step == AnalysisStep.GUIDE_GENERATION)
        out["retryCount"] = a.retry_count
    else:
        out["drugCount"], out["excludedCount"] = await _counts(a)
        out["estimatedSeconds"] = ESTIMATED_SECONDS
    return out


async def prepare_retry(user: User, analysis_id: int) -> tuple[Analysis, AnalysisStep]:
    a = await _expire_if_stuck(await _get(user, analysis_id))
    if a.status != AnalysisStatus.FAILED:
        raise AppError(status.HTTP_409_CONFLICT, "ANALYSIS_NOT_FAILED", "실패한 분석이 아니에요.")
    if a.retry_count >= MAX_RETRIES:
        raise AppError(status.HTTP_429_TOO_MANY_REQUESTS, "RETRY_LIMIT_EXCEEDED", "잠시 후 다시 시도해 주세요.")
    start = a.failed_step or AnalysisStep.DRUG_INFO
    n = await Analysis.filter(id=a.id, status=AnalysisStatus.FAILED, retry_count=a.retry_count).update(
        status=AnalysisStatus.QUEUED,
        retry_count=a.retry_count + 1,
        error_code=None,
        failed_step=None,
        current_step=start,
        started_at=_now(),
        finished_at=None,
    )
    if not n:  # 동시에 두 번 눌렀을 때
        raise AppError(status.HTTP_409_CONFLICT, "ANALYSIS_NOT_FAILED", "실패한 분석이 아니에요.")
    return a, start


# ── R-4 결과 ──────────────────────────────────────────────────────────────────────────────────
def _drug_ref(it: PrescriptionItem) -> dict[str, Any]:
    return {
        "ediCode": it.drug.edi_code if it.drug else None,
        "itemName": base_name(it.drug.item_name) if it.drug else it.raw_name,
        "hospitalName": it.prescription.hospital_name,
    }


async def _warning_rows(a: Analysis) -> list[AnalysisWarning]:
    rows = await AnalysisWarning.filter(analysis=a).order_by("id")
    return sorted(rows, key=lambda w: (SEVERITY_ORDER.get(w.severity, 9), w.id))


async def _items_by_id(a: Analysis) -> dict[int, PrescriptionItem]:
    return {i.id: i for i in await _items(a)}


def _warning_item_ids(w: AnalysisWarning) -> list[int]:
    ids = (w.detail or {}).get("itemIds") or [x for x in (w.item_a_id, w.item_b_id) if x]  # type: ignore[attr-defined]
    return [int(x) for x in ids]


def _source(w: AnalysisWarning) -> dict[str, Any]:
    return {"name": w.source, "noticeDate": w.notice_date.isoformat() if w.notice_date else None}


def _warning_card(w: AnalysisWarning, by_id: dict[int, PrescriptionItem]) -> dict[str, Any]:
    return {
        "id": w.id,
        "type": w.warning_type,
        "severity": w.severity,
        "title": TITLES.get(w.warning_type, "확인이 필요해요"),
        "drugs": [_drug_ref(by_id[i]) for i in _warning_item_ids(w) if i in by_id],
        "summary": w.summary,
        "source": _source(w),
    }


async def _guide_content(a: Analysis, section: GuideSection) -> tuple[int, str, dict[str, Any] | None]:
    g = await Guide.get_or_none(analysis=a, section=section)
    if g is None or g.status != GuideStatus.DONE:
        return (g.id if g else 0), "failed", None
    return g.id, "done", g.content


def _empty_lifestyle() -> dict[str, Any]:
    return {"diseases": [], "medicationLinks": [], "sections": [], "warningSigns": [], "sources": []}


async def _lifestyle_view(a: Analysis, content: dict[str, Any] | None) -> dict[str, Any]:
    origin = {d.disease_id: d.origin.value for d in await AnalysisDisease.filter(analysis=a)}  # type: ignore[attr-defined]
    body = content or _empty_lifestyle()
    return {**body, "diseases": [{**d, "origin": origin.get(d["code"], "prescription")} for d in body["diseases"]]}


def _checked_count(items: list[PrescriptionItem]) -> int:
    """점검한 약 수 — 확인이 끝난 약에서 외용약(점검에서 빠짐)을 뺀 수"""
    return sum(1 for i in items if i.match_status in USABLE and i.drug and i.drug.route == "내복")


async def get_result(user: User, analysis_id: int) -> dict[str, Any]:
    a = await _expire_if_stuck(await _get(user, analysis_id))
    partial = a.status == AnalysisStatus.FAILED and a.failed_step == AnalysisStep.GUIDE_GENERATION
    if a.status != AnalysisStatus.DONE and not partial:
        raise AppError(status.HTTP_409_CONFLICT, "ANALYSIS_NOT_READY", "아직 분석 중이에요.")
    items = await _items(a)
    by_id = {i.id: i for i in items}
    usable = [i for i in items if i.match_status in USABLE and i.drug]
    rows = await _warning_rows(a)
    rxs = await Prescription.filter(analyses__analysis=a).order_by("id")  # type: ignore[misc]
    hospitals = list(dict.fromkeys(r.hospital_name for r in rxs if r.hospital_name))
    excluded = [
        {"rawName": i.raw_name, "reason": "excluded" if i.match_status == MatchStatus.EXCLUDED else "unmatched"}
        for i in items
        if i.match_status not in USABLE
    ] + [{"rawName": base_name(i.drug.item_name), "reason": "not_oral"} for i in usable if i.drug.route != "내복"]
    checked = _checked_count(items)
    med_id, med_status, med = await _guide_content(a, GuideSection.MEDICATION)
    life_id, life_status, life = await _guide_content(a, GuideSection.LIFESTYLE)
    counts = Counter(w.severity for w in rows)
    return {
        "analysisId": a.id,
        "status": a.status.value,
        "createdAt": a.created_at.isoformat(),
        "summary": {
            "prescriptionCount": len(rxs),
            "hospitals": hospitals,
            "drugCount": checked,
            "warningCounts": {k: counts.get(k, 0) for k in ("danger", "caution", "info")},
        },
        "excludedDrugs": excluded,
        "warnings": [_warning_card(w, by_id) for w in rows],
        "checkedItems": [{"type": t, "label": label, "state": "checked"} for t, label in CHECKED_ITEMS],
        "medication": {"guideId": med_id, "status": med_status, **(med or {"items": []})},
        "lifestyle": {"guideId": life_id, "status": life_status, **await _lifestyle_view(a, life)},
        "disclaimer": DISCLAIMER,
    }


# ── R-5 경고 자세히 ───────────────────────────────────────────────────────────────────────────
async def get_warning(user: User, analysis_id: int, warning_id: int) -> dict[str, Any]:
    a = await _get(user, analysis_id)
    w = await AnalysisWarning.get_or_none(id=warning_id, analysis=a)
    if w is None:
        raise AppError(status.HTTP_404_NOT_FOUND, "NOT_FOUND")
    by_id = await _items_by_id(a)
    refs = [by_id[i] for i in _warning_item_ids(w) if i in by_id]
    try:
        names = await asyncio.to_thread(safety.ingredient_names, [r.drug.edi_code for r in refs if r.drug])
    except safety.SafetyDbMissingError:
        names = {}
    dose = None
    if w.warning_type == "dose_exceed" and w.daily_total is not None:
        dose = {"dailyTotal": float(w.daily_total), "maxDaily": float(w.max_daily) if w.max_daily is not None else None}
    return {
        "id": w.id,
        "type": w.warning_type,
        "severity": w.severity,
        "title": TITLES.get(w.warning_type, "확인이 필요해요"),
        "drugs": [
            {
                "itemName": base_name(r.drug.item_name) if r.drug else r.raw_name,
                "hospitalName": r.prescription.hospital_name,
                "category": medication.category_of(r.drug),
                "ingredient": names.get(r.drug.edi_code) if r.drug else None,
            }
            for r in refs
        ],
        "explanation": w.summary,
        "reasonOriginal": w.reason,
        "source": _source(w),
        "judgedBy": "database",
        "doseDetail": dose,
        "actionAdvice": ACTION_ADVICE.get(w.warning_type, DEFAULT_ADVICE),
    }


# ── R-6 질환 직접 선택 ────────────────────────────────────────────────────────────────────────
async def put_diseases(user: User, analysis_id: int, codes: list[str]) -> dict[str, Any]:
    a = await _expire_if_stuck(await _get(user, analysis_id))
    if a.status != AnalysisStatus.DONE and not (
        a.status == AnalysisStatus.FAILED and a.failed_step == AnalysisStep.GUIDE_GENERATION
    ):
        raise AppError(status.HTTP_409_CONFLICT, "ANALYSIS_NOT_READY", "아직 분석 중이에요.")
    wanted = list(dict.fromkeys(c.strip().upper() for c in codes if c.strip()))
    known = set(await Disease.filter(code__in=wanted).values_list("code", flat=True)) if wanted else set()
    bad = [c for c in wanted if c not in known]
    if bad:
        raise AppError(
            status.HTTP_400_BAD_REQUEST, "VALIDATION_ERROR", "알 수 없는 질병분류기호가 있어요.", field="diseaseCodes"
        )
    items = [i for i in await _items(a) if i.match_status in USABLE and i.drug]
    async with in_transaction():
        await AnalysisDisease.filter(analysis=a).delete()
        for c in wanted:
            await AnalysisDisease.create(analysis=a, disease_id=c, origin=DiseaseOrigin.USER)
        content = lifestyle.build(wanted, items)
        await Guide.update_or_create(
            analysis=a,
            section=GuideSection.LIFESTYLE,
            defaults={"status": GuideStatus.DONE, "content": content},
        )
    return await _lifestyle_view(a, content)


# ── R-7 지난 기록 목록 ────────────────────────────────────────────────────────────────────────
LIST_DEFAULT_SIZE = 20
LIST_MAX_SIZE = 50
RESULT_LABELS = {"running": "분석 중", "failed": "분석 실패", "clean": "확인된 위험 없음"}


def _encode_cursor(analysis_id: int) -> str:
    return (
        base64.urlsafe_b64encode(json.dumps({"id": analysis_id}, separators=(",", ":")).encode()).decode().rstrip("=")
    )


def _decode_cursor(cursor: str) -> int:
    try:
        return int(json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))["id"])
    except (ValueError, KeyError, TypeError) as e:
        raise AppError(
            status.HTTP_400_BAD_REQUEST, "VALIDATION_ERROR", "다음 목록을 불러오지 못했어요.", field="cursor"
        ) from e


def _list_status(a: Analysis) -> str:
    if a.status == AnalysisStatus.DONE:
        return "done"
    return "failed" if a.status == AnalysisStatus.FAILED else "running"


async def list_analyses(user: User, cursor: str | None, size: int) -> dict[str, Any]:
    """최신순으로 size개. 다음 쪽이 있으면 nextCursor를 줌 (분석 ID 기준이라 새 기록이 생겨도 밀리지 않음)"""
    size = max(1, min(size, LIST_MAX_SIZE))
    query = Analysis.filter(user=user)
    if cursor:
        query = query.filter(id__lt=_decode_cursor(cursor))
    rows = await query.order_by("-id").limit(size + 1)
    has_more = len(rows) > size
    rows = [await _expire_if_stuck(a) for a in rows[:size]]
    done_ids = [a.id for a in rows if a.status == AnalysisStatus.DONE]

    rx_by_analysis: dict[int, list[int]] = {}
    for analysis_id, rx_id in await AnalysisPrescription.filter(analysis_id__in=done_ids).values_list(
        "analysis_id", "prescription_id"
    ):
        rx_by_analysis.setdefault(analysis_id, []).append(rx_id)
    all_rx = [r for ids in rx_by_analysis.values() for r in ids]
    hospital_of = dict(await Prescription.filter(id__in=all_rx).values_list("id", "hospital_name"))
    items_by_rx: dict[int, list[PrescriptionItem]] = {}
    for it in await PrescriptionItem.filter(prescription_id__in=all_rx).prefetch_related("drug"):
        items_by_rx.setdefault(it.prescription_id, []).append(it)  # type: ignore[attr-defined]
    warning_counts: Counter[int] = Counter(
        await AnalysisWarning.filter(analysis_id__in=done_ids).values_list("analysis_id", flat=True)  # type: ignore[arg-type]
    )
    names: dict[int, list[str]] = {}
    for g in await Guide.filter(analysis_id__in=done_ids, section=GuideSection.LIFESTYLE, status=GuideStatus.DONE):
        names[g.analysis_id] = [d["name"] for d in (g.content or {}).get("diseases", [])]  # type: ignore[attr-defined]
    fallback_ids = [i for i in done_ids if not names.get(i)]
    for analysis_id, name in await AnalysisDisease.filter(analysis_id__in=fallback_ids).values_list(
        "analysis_id", "disease__name_kr"
    ):
        names.setdefault(analysis_id, []).append(name)

    items = []
    for a in rows:
        row: dict[str, Any] = {"analysisId": a.id, "createdAt": a.created_at.isoformat(), "status": _list_status(a)}
        if a.status == AnalysisStatus.DONE:
            rx_ids = rx_by_analysis.get(a.id, [])
            n = warning_counts.get(a.id, 0)
            row["hospitals"] = list(dict.fromkeys(hospital_of[r] for r in rx_ids if hospital_of.get(r)))
            row["drugCount"] = _checked_count([it for r in rx_ids for it in items_by_rx.get(r, [])])
            row["diseaseNames"] = names.get(a.id, [])
            row["resultLabel"] = f"확인 필요 {n}건" if n else RESULT_LABELS["clean"]
        else:
            row["resultLabel"] = RESULT_LABELS[row["status"]]
        items.append(row)
    return {"items": items, "nextCursor": _encode_cursor(rows[-1].id) if has_more and rows else None}


# ── R-8 기록 삭제 ─────────────────────────────────────────────────────────────────────────────
async def delete_analysis(user: User, analysis_id: int) -> None:
    """분석 결과 · 경고 · 안내문 · 피드백을 지우고, 이 분석에만 쓰인 처방전(약 포함)도 같이 지움 (다른 분석에도 쓰였으면 남김).
    챗봇 대화와 실천 목표는 아직 서버에 없어서 여기서 다루지 않음 (생기면 이어서 처리)"""
    a = await _expire_if_stuck(await _get(user, analysis_id))
    if a.status in (AnalysisStatus.QUEUED, AnalysisStatus.RUNNING):
        raise AppError(
            status.HTTP_409_CONFLICT, "ANALYSIS_RUNNING", "분석이 끝난 뒤에 지울 수 있어요. 잠시 후 다시 해 주세요."
        )
    async with in_transaction():
        rx_ids = list(await AnalysisPrescription.filter(analysis=a).values_list("prescription_id", flat=True))
        await Analysis.filter(id=a.id).delete()  # 경고 · 안내문 · 피드백 · 연결 표는 DB가 같이 지움 (ON DELETE CASCADE)
        still_used = set(
            await AnalysisPrescription.filter(prescription_id__in=rx_ids).values_list("prescription_id", flat=True)
        )
        only_here = [r for r in rx_ids if r not in still_used]
        if only_here:
            await Prescription.filter(id__in=only_here, user=user).delete()


# ── R-9 안내문 피드백 ─────────────────────────────────────────────────────────────────────────
async def save_feedback(user: User, guide_id: int, rating: int, comment: str | None) -> int:
    """한 사람이 안내문 하나에 하나만 남김 — 다시 보내면 앞의 것을 덮어씀"""
    guide = await Guide.get_or_none(id=guide_id, analysis__user_id=user.id)
    if guide is None:
        raise AppError(status.HTTP_404_NOT_FOUND, "NOT_FOUND")
    text = (comment or "").strip() or None
    fb, _ = await GuideFeedback.update_or_create(guide=guide, user=user, defaults={"rating": rating, "comment": text})
    return fb.id
