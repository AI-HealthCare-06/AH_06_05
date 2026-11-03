"""피처 3 챗봇 서비스 (API H-1 ~ H-8, #100)

질문 보내기(H-3): 1층과 문맥 파악(AI 없음)을 저장 전에 보고, 막을 질문이면 원문 없이 긴급 답 줄을 바로 만듦.
아니면 질문 줄과 만드는 중(generating) 답 줄을 만들고 202를 돌려준 뒤, 뒤에서 답을 끝까지 만들어 한 번에 저장함.
지금은 FastAPI 백그라운드 작업으로 돌리고, 10/26 워커 이전 뒤 arq로 옮김 (#118).
질문 원문은 로그에 남기지 않음.
"""

import asyncio
import logging
from datetime import date, datetime, timedelta
from typing import Any

from starlette import status

from app.core import config
from app.core.errors import AppError
from app.models.analysis import (
    Analysis,
    AnalysisDisease,
    AnalysisPrescription,
    AnalysisStatus,
    AnalysisWarning,
    DrugGuide,
    ReviewStatus,
)
from app.models.chat import AnswerType, ChatMessage, ChatPhotoUse, ChatSession, MessageRole, MessageStatus
from app.models.ocr import MatchStatus, PrescriptionItem
from app.models.users import ConsentType, User, UserConsent
from app.repositories.chat import ChatRepository
from app.services import chat_photo, safety
from app.services.chatbot import jev, pipeline, safety_rules
from app.services.chatbot.answer import DISTRESS
from app.services.chatbot.context import FixedInfo, PairWarning, UserDrug, find_drug
from app.services.chatbot.evidence import JOB_LIMIT_SEC
from app.services.chatbot.llm import make_client
from app.services.chatbot.pipeline import Reply, Route
from app.services.drug_names import display_name
from app.services.guide import lifestyle, medication
from app.services.ocr import clova
from app.services.ocr.mask import mask_numbers
from app.services.prescriptions import check_photo_limit, has_health_consent, search_drugs, validate_uploads

logger = logging.getLogger(__name__)
repo = ChatRepository()

# 답 만들기 전체를 이 안에서 끊음. 분류와 답 만들기를 차례로 부르면 15초 + 15초로 넘을 수 있어서 (10/22)
ANSWER_TIMEOUT_SEC = JOB_LIMIT_SEC
STALE_SEC = 30  # 만드는 중으로 이보다 오래된 답 줄은 다시 시도 때 지우고 새로 만듦 (명세서 H-3)
USABLE = (MatchStatus.AUTO, MatchStatus.USER_CONFIRMED)
DRUG_SOURCE = "식약처 의약품 허가정보"  # 근거 번호 D:<약코드>:S12 (허가정보 문장)


WARNING_FIRST_TAIL = "처방한 의사나 약사에게 꼭 알려 주세요."  # 설계 메모 4-4, 6-1 E2 첫 답변
# CB-03 대화 카드 (제안). 제목을 고치지 않은 대화는 첫 질문 앞부분을 보임
TITLE_MAX = 30
PREVIEW_MAX = 60
DEFAULT_TITLE = "대화"


def _now() -> datetime:
    return datetime.now(config.TIMEZONE)


def _next_midnight() -> datetime:
    return (_now() + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)


async def _session(user: User, session_id: int) -> ChatSession:
    s = await repo.get_session(user, session_id)
    if s is None:
        raise AppError(status.HTTP_404_NOT_FOUND, "NOT_FOUND")
    return s


async def _check_analysis(user: User, analysis_id: int) -> None:
    if not await Analysis.exists(id=analysis_id, user=user):
        raise AppError(status.HTTP_404_NOT_FOUND, "NOT_FOUND")


# ── H-1 대화 시작, H-8 오늘 대화, H-6 삭제 ──────────────────────────────────────────────────
async def start_session(
    user: User, client_request_id: str, analysis_id: int | None, context: dict[str, Any] | None
) -> int:
    """analysisId는 대화에만 적고 맥락 카드 줄은 만들지 않음 (카드는 H-7에서만)"""
    if analysis_id is not None:
        await _check_analysis(user, analysis_id)
    s = await repo.get_session_by_request(user, client_request_id)
    if s is None:
        s = await repo.create_session(
            user,
            client_request_id,
            analysis_id=analysis_id,
            context_type=context["type"] if context else None,
            context_ref=context["id"] if context else None,
        )
    return s.id


async def today(user: User) -> dict[str, Any]:
    start = _now().replace(hour=0, minute=0, second=0, microsecond=0)
    s = await repo.last_session_since(user, start)
    until = await repo.safety_until(user, _now())
    return {
        "sessionId": s.id if s else None,
        "hasHistory": await repo.has_session(user),
        "safetyModeUntil": until.isoformat() if until else None,
    }


def _kst_midnight(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, tzinfo=config.TIMEZONE)


async def days_with_sessions(user: User, month: str) -> dict[str, Any]:
    """H-4 ?month=2026-09: 그달에 대화를 시작한 날짜 (CB-02)"""
    try:
        first = datetime.strptime(month, "%Y-%m").date()
    except ValueError as e:
        raise _bad_period("month") from e
    next_first = (first + timedelta(days=32)).replace(day=1)
    rows = await repo.sessions_between(user, _kst_midnight(first), _kst_midnight(next_first))
    return {"dates": sorted({r.created_at.astimezone(config.TIMEZONE).date().isoformat() for r in rows})}


async def sessions_on(user: User, day: str) -> dict[str, Any]:
    """H-4 ?date=2026-09-16: 그날 시작한 대화 (CB-03). 제목을 고치지 않았으면 첫 질문 앞부분"""
    try:
        d = datetime.strptime(day, "%Y-%m-%d").date()
    except ValueError as e:
        raise _bad_period("date") from e
    rows = await repo.sessions_between(user, _kst_midnight(d), _kst_midnight(d + timedelta(days=1)))
    first = await repo.first_questions([r.id for r in rows])
    return {
        "items": [
            {
                "sessionId": r.id,
                "title": r.title or first.get(r.id, "")[:TITLE_MAX] or DEFAULT_TITLE,
                "preview": first.get(r.id, "")[:PREVIEW_MAX],
                "createdAt": r.created_at.astimezone(config.TIMEZONE).isoformat(),
                "updatedAt": r.updated_at.astimezone(config.TIMEZONE).isoformat(),
            }
            for r in rows
        ]
    }


def _bad_period(field: str) -> AppError:
    return AppError(status.HTTP_400_BAD_REQUEST, "VALIDATION_ERROR", "날짜 형식이 맞지 않아요.", field=field)


async def rename_session(user: User, session_id: int, title: str) -> dict[str, Any]:
    """H-5 대화 제목 수정"""
    s = await _session(user, session_id)
    await repo.set_title(s.id, title)
    return {"sessionId": s.id, "title": title}


async def _delete(s: ChatSession) -> None:
    """지워도 안전 모드는 풀리지 않게, 켜져 있는 대화는 글만 지움 (설계 메모 4-6)"""
    if s.safety_mode_until and s.safety_mode_until > _now():
        await repo.clear_session(s)
    else:
        await repo.delete_session(s)


async def delete_session(user: User, session_id: int) -> None:
    await _delete(await _session(user, session_id))


async def delete_all_sessions(user: User) -> None:
    """MY-S1 전체 삭제"""
    for s in await repo.sessions_of(user):
        await _delete(s)


# ── H-2 이전 대화 ──────────────────────────────────────────────────────────────────────────
def _item(m: ChatMessage) -> dict[str, Any]:
    """칸이 해당하지 않으면 생략 (null로 보내지 않음). 측정값(model, 토큰, 시간)은 내려주지 않음"""
    row: dict[str, Any] = {"id": m.id, "role": m.role.value, "content": m.content}
    if m.answer_type:
        row["answerType"] = m.answer_type.value
    row["status"] = m.status.value
    if m.reply_to_id:
        row["replyTo"] = m.reply_to_id
    if m.answer_type:
        row["sources"] = m.sources or []
    for key, value in (
        ("contextCard", m.context_card),
        ("safetyCard", m.safety_card),
        ("safety", m.safety),
        ("chips", m.chips),
        ("drugMatch", m.drug_match),
        ("imageResult", m.image_result),
    ):
        if value:
            row[key] = value
    if m.image_result == chat_photo.PRESCRIPTION:
        row["action"] = "open_analysis"  # 앱이 [처방전 · 약봉투 분석하러 가기]를 보임
    if m.answer_type and (m.content == DISTRESS or m.image_result):
        # 범위 밖 괴로움의 도움 연결 답(#144 채연 리뷰, #117)과 사진 첨부 안내(규칙으로 만든 답, #199 채연 리뷰)에는 피드백 버튼을 두지 않음
        row["noFeedback"] = True
    row["createdAt"] = m.created_at.isoformat()
    return row


async def messages(user: User, session_id: int) -> dict[str, Any]:
    return {"items": [_item(m) for m in await repo.messages(await _session(user, session_id))]}


# ── H-7 맥락 카드 ──────────────────────────────────────────────────────────────────────────
async def add_context(
    user: User, session_id: int, analysis_id: int, context: dict[str, Any] | None, client_request_id: str
) -> dict[str, Any]:
    """같은 clientRequestId면 줄을 새로 만들지 않고 처음 만든 첫 답을 돌려줌. 첫 답은 경고나 약을 고른 카드에만 있음"""
    s = await _session(user, session_id)
    await _check_analysis(user, analysis_id)
    card_row = await repo.get_by_request(s, client_request_id)
    if card_row:
        first = await repo.first_message_after(card_row)
        return {"firstMessage": _item(first)} if first else {}
    card: dict[str, Any] = {"analysisId": analysis_id}
    if context:
        card["context"] = context
    made = await _first_message(user, analysis_id, context) if context else None
    if made is None:
        await repo.create_card(s, client_request_id, card)
        return {}
    first = await repo.create_card_with_answer(s, client_request_id, card, *made)
    return {"firstMessage": _item(first)}


async def _first_message(
    user: User, analysis_id: int, context: dict[str, Any]
) -> tuple[str, list[dict[str, str]]] | None:
    """맥락 카드의 첫 답 (설계 메모 4-4). 분석 결과에 있는 글로만 만들고 AI를 부르지 않음 (경고 문구는 NFR-032).
    민감정보 동의가 없거나 그 분석에 없는 번호면 없음"""
    if not await has_health_consent(user):
        return None
    if context["type"] == "warning":
        return await _warning_first(analysis_id, context["id"])
    return await _drug_first(analysis_id, context["id"])


async def _warning_first(analysis_id: int, warning_id: int) -> tuple[str, list[dict[str, str]]] | None:
    w = await AnalysisWarning.get_or_none(id=warning_id, analysis_id=analysis_id).prefetch_related(
        "item_a__drug", "item_b__drug"
    )
    if w is None or not w.summary:
        return None
    names = ", ".join(_item_name(it) for it in (w.item_a, w.item_b) if it)
    text = f"{names}: {w.summary}" if names else w.summary
    reason = (w.reason or "").strip(" -")  # DUR 사유. 쉬운 말로 바꾸지 않고 경고 자세히 화면(RG-03)처럼 원문 그대로
    if reason:
        text += f"\n원문: {reason}"
    source = {"title": w.source, **({"basedOn": w.notice_date.isoformat()} if w.notice_date else {})}  # 고시일
    return f"{text}\n\n{WARNING_FIRST_TAIL}", [source] if w.source else []


def _drug_first_sources(guide: DrugGuide | None) -> list[dict[str, str]]:
    """안내문에 허가정보 출처가 적혀 있으면 그것을 (시연 약, 복약 안내 카드와 같게). 약효분류 표에서 나온 쓰임이면 표 이름과 기준일 (#193 채연 리뷰)"""
    source = (guide.content or {}).get("source") if guide else None
    if source and source != medication.SOURCE:
        return [{"title": source}]
    return [{"title": medication.SOURCE, "basedOn": medication.SOURCE_DATE}]


async def _drug_first(analysis_id: int, item_id: int) -> tuple[str, list[dict[str, str]]] | None:
    rx_ids = await AnalysisPrescription.filter(analysis_id=analysis_id).values_list("prescription_id", flat=True)
    it = await PrescriptionItem.get_or_none(id=item_id, prescription_id__in=list(rx_ids)).prefetch_related("drug")
    if it is None or it.drug is None:
        return None
    guide = await DrugGuide.get_or_none(edi_code=it.drug.edi_code, review_status=ReviewStatus.APPROVED)
    purpose = (guide.content or {}).get("purpose") if guide else None
    how = medication.how_to_take(it, it.drug)
    lines = [f"{purpose}." if purpose else None, f"먹는 법: {how}" if how else None]
    body = "\n".join(x for x in lines if x)
    if not body:
        return None
    return f"{_item_name(it)}\n{body}", _drug_first_sources(guide) if purpose else []


# ── H-3 질문 보내기 ────────────────────────────────────────────────────────────────────────
def _safety(r: Route) -> dict[str, Any]:
    """원문 없이 걸린 갈래와 규칙 이름만 (명세서 H-3 safety, 설계 메모 SafetyInfo.rule은 글자 하나라 쉼표로 이음)"""
    return {"types": r.safety_types, "overdose": r.overdose, "rule": ",".join(r.safety_rules)}


async def _check_daily_limit(user: User) -> None:
    """하루 질문 수가 상한에 닿으면 429. 1층을 지난 질문만 세고, 1층에 걸린 긴급과 자해는 여기까지 오지 않음 (#116)"""
    limit = config.CHAT_DAILY_QUESTION_LIMIT
    if limit <= 0:
        return
    used = await repo.questions_since(user, _now().replace(hour=0, minute=0, second=0, microsecond=0))
    if used >= limit:
        raise AppError(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "DAILY_LIMIT_EXCEEDED",
            "오늘 질문을 다 쓰셨어요. 내일 다시 물어봐 주세요. 급한 내용은 약사나 의료진에게 확인해 주세요.",
            detail={"limit": limit, "used": used},
        )


async def ask(
    user: User, session_id: int, content: str, client_request_id: str, emergency_dismissed: bool
) -> tuple[int, bool]:
    """답 줄 번호와, 뒤에서 답을 만들어야 하는지를 돌려줌"""
    s = await _session(user, session_id)
    question = await repo.get_by_request(s, client_request_id)
    if question:  # 다시 시도 (CB-01-E6)
        last = await repo.last_answer_to(question)
        if last and not (
            last.status == MessageStatus.GENERATING and last.created_at < _now() - timedelta(seconds=STALE_SEC)
        ):
            return last.id, False
        if last:
            await repo.delete_message(last.id)
        return (await repo.create_generating(question)).id, True

    blocked, release = pipeline.first_layer(content, emergency_dismissed)
    if not blocked and safety_rules.asks_amount(content) and await repo.safety_until(user, _now()):
        # 안전 모드(자정까지, 지난 대화를 열어도 같음)에서는 약의 양 질문을 처방대로 묻더라도 E5로 (설계 메모 4-6, 7-2, #116)
        blocked = Route(kind="crisis", layer=1, safety_types=["crisis"], safety_rules=["safety_mode_amount"])
    # 규칙에 안 걸리고 문맥 파악이 풀지도 않은 질문만 Jev에게 (10/26 수인 결정). TypeSafe(미국) 전달에 동의한 사람만 (11/2 수인 결정)
    if not blocked and release is None and jev.enabled() and await _has_risk_check_consent(user):
        blocked = await pipeline.jev_layer(mask_numbers(content), emergency_dismissed)  # 번호, 이메일은 가려서 보냄
    if blocked:  # 1층(규칙이나 Jev)이 잡고 문맥 파악이 풀지 않음: 원문을 저장하지 않고 긴급 답을 바로 (설계 메모 4-6)
        answer = await repo.create_question_and_answer(
            s,
            "",
            client_request_id,
            answer_type=AnswerType(blocked.kind),
            safety=_safety(blocked),
            route_kind=blocked.kind,
        )
        if "crisis" in blocked.safety_types:
            await repo.set_safety_mode(s.id, _next_midnight())
        return answer.id, False
    await _check_daily_limit(user)
    # 입력 정책: 주민번호, 전화번호 같은 번호는 저장과 OpenAI로 가기 전에 가림. 1층은 위에서 원문을 봄 (10/31 수인 결정)
    answer = await repo.create_question_and_answer(
        s, mask_numbers(content), client_request_id, status=MessageStatus.GENERATING
    )
    return answer.id, True


async def run_pipeline(
    question: str,
    info: FixedInfo,
    history: list[dict[str, str]],
    emergency_dismissed: bool = False,
    recent: list[str] | None = None,
) -> Reply:
    """답 만들기 (OpenAI). 시험에서는 가짜로 바꿈. recent는 2층에 참고로 주는 앞 사용자 말"""
    return await pipeline.answer(
        question,
        info,
        history,
        make_client(),
        emergency_dismissed=emergency_dismissed,
        match=_drug_match,
        recent=recent,
    )


async def _drug_match(name: str) -> dict[str, Any] | None:
    """질문의 약 이름을 O-4와 같은 이름 맞추기로 찾음. 목록을 못 읽으면 없는 것으로 (답은 계속 만듦)"""
    try:
        return await search_drugs(name, 3)
    except Exception:  # noqa: BLE001  이름 맞추기 실패가 답을 막지 않게
        logger.warning("drug_match 실패", exc_info=True)
        return None


def _fact_sources(sentence_id: str) -> list[str]:
    """F:<질환 id>:life:<항목 이름>은 lifestyle_facts.json 그 질환 생활습관 항목(category)의 출처 (조각 파일 번호 모양, #119 채연 리뷰).
    출처 글은 R-4 생활습관과 같게 " / "로 나눔. 목표 수치(target), 약 연결(med), 위험 신호(warn), 질환 겹침(cross)은 출처 칸이 없어 뺌"""
    parts = sentence_id.split(":", 3)
    if len(parts) != 4 or parts[2] != "life":
        return []
    d = next((x for x in lifestyle.facts()["diseases"] if x["id"] == parts[1]), None)
    item = next((x for x in d["lifestyle"] if x["category"] == parts[3]), None) if d else None
    return [p.strip() for p in ((item or {}).get("source") or "").split(" / ") if p.strip()]


def _sources(ids: list[str]) -> list[dict[str, str]]:
    """근거 번호 → 출처 이름. 허가정보(D)와 팩트표 생활습관(F:...:life:...)만 출처가 있음"""
    titles: list[str] = []
    for i in ids:
        kind = i.split(":")[0]
        titles += (
            [DRUG_SOURCE] if kind == "D" else _fact_sources(i) if kind == "F" else ["처방전"] if kind == "P" else []
        )
    return [{"title": t} for t in dict.fromkeys(titles)]


async def _has_risk_check_consent(user: User) -> bool:
    """위험 판단 AI(TypeSafe, 미국) 전달에 동의했는지 (선택 동의, 11/2)"""
    return await UserConsent.filter(
        user=user, consent_type=ConsentType.RISK_CHECK, agreed=True, withdrawn_at=None
    ).exists()


async def add_photo(
    user: User, session_id: int, client_request_id: str, filename: str, content: bytes
) -> dict[str, Any]:
    """H-9 사진 첨부 (CB-04). 사진 한 장을 OCR로 읽어 사용자 줄과 답 줄을 한 번에 만듦. 사진과 읽은 글자는 저장하지 않음.
    같은 clientRequestId면 새로 만들지 않고 처음의 답 줄 번호를 돌려줌"""
    s = await _session(user, session_id)
    if (first := await repo.get_by_request(s, client_request_id)) and (done := await repo.last_answer_to(first)):
        return {"messageId": done.id}
    blob = validate_uploads([(filename, content)])[0]
    if not await has_health_consent(user):
        raise AppError(
            status.HTTP_403_FORBIDDEN, "CONSENT_REQUIRED", "건강 정보 사용에 동의해야 사진을 보낼 수 있어요."
        )
    await _check_daily_limit(user)
    await check_photo_limit(user)  # O-1과 합산한 하루 사진 상한 (CLOVA 호출 전에)
    await ChatPhotoUse.create(user=user)  # CLOVA를 부르기 전에 남김 (읽기에 실패해도 한 번 쓴 것)
    try:
        result = await chat_photo.identify(blob)
    except clova.ClovaError as e:
        logger.warning("챗봇 사진 OCR 실패 (%s)", e)  # 사진과 글자는 남기지 않음
        raise AppError(
            status.HTTP_502_BAD_GATEWAY, "OCR_FAILED", "사진을 읽지 못했어요. 잠시 후 다시 시도해 주세요."
        ) from e
    answer = await repo.create_photo_pair(
        s, client_request_id, chat_photo.PHOTO_TEXT, {"route_kind": "image", **chat_photo.answer_fields(result)}
    )
    return {"messageId": answer.id}


def _recent_user_turns(rows: list[ChatMessage]) -> list[str]:
    """2층에 참고로 줄 최근 사용자 말 (#143). 범위 밖으로 걸러진 말도 넣음(괴로움이 범위 밖으로 간 경우).
    1층이 잡아 원문이 없는 말과 사진 첨부 줄은 빠짐"""
    photos = {m.reply_to_id for m in rows if m.route_kind == "image"}  # 사진 첨부의 사용자 줄은 고정 글이라 뺌
    turns = [m.content for m in rows if m.role == MessageRole.USER and m.content and m.id not in photos]
    return turns[-2:]


def _history(rows: list[ChatMessage]) -> list[dict[str, str]]:
    """빈 글 줄(1층이 잡은 질문, 긴급 답, 맥락 카드)은 대화 기억에 넣지 않음.
    범위 밖으로 걸러진 질문과 그 답도 뺌. 앞 대화가 다음 답의 노이즈가 됨 (5회차 멘토링 시연, #99)"""
    out = ("out_of_scope", "image")  # 사진 첨부(안내 답)도 다음 답의 노이즈라 뺌
    skip = {m.reply_to_id for m in rows if m.route_kind in out}
    return [
        {"role": m.role.value, "content": m.content}
        for m in rows
        if m.content and m.route_kind not in out and m.id not in skip
    ]


async def generate(message_id: int, emergency_dismissed: bool = False) -> None:
    """뒤에서 답을 끝까지 만들어 한 번에 저장. 실패하면 만드는 중이던 답 줄을 지움 (failed는 두지 않음)"""
    answer = await repo.get_generating(message_id)
    if answer is None:
        return
    question, s = answer.reply_to, answer.session
    if question is None:  # 답 줄은 늘 질문 줄을 가리킴
        await repo.delete_message(answer.id)
        return
    try:
        info = await fixed_info(s.user, s)
        before = await repo.done_messages_before(s.id, question.id)
        info.focus_drug, info.focus_warning = await _card_focus(info, before)
        history = _history(before)
        recent = _recent_user_turns(before)
        reply: Reply | None = await asyncio.wait_for(
            run_pipeline(question.content, info, history, emergency_dismissed, recent=recent), ANSWER_TIMEOUT_SEC
        )
    except Exception as e:  # noqa: BLE001 - 어떤 실패든 답 줄을 지워 앱이 E6을 보이게 함
        logger.warning("챗봇 답 만들기 실패: %s", type(e).__name__)  # 예외 문장에 질문이 섞일 수 있어 종류 이름만
        reply = None
    if reply is None or reply.answer_type == "error":
        await repo.delete_message(answer.id)
        return
    r = reply.route
    if reply.evidence_reason:
        # 근거 없음 원인(no_candidate 등)을 서버 로그로 찾게 (10/25). 질문 글과 약 이름은 남기지 않고 개수만.
        # 서버는 이 로거에 출력 설정이 없어 WARNING부터 보이므로 warning으로 남김
        logger.warning(
            "챗봇 근거 없음 message=%s answer_type=%s kind=%s reason=%s verdicts=%s drugs=%s diseases=%s",
            answer.id, reply.answer_type, r.kind, reply.evidence_reason, reply.evidence_verdicts,
            len(info.drugs), len(info.disease_ids),
        )  # fmt: skip
    saved = await repo.finish(
        answer.id,
        AnswerType(reply.answer_type),
        content=reply.content or "",
        sources=_sources(reply.sources),
        safety=_safety(r) if r.safety_types else None,
        safety_card=reply.safety_card,
        chips=reply.chips or None,
        drug_match=reply.drug_match,
        route_kind=r.kind,
        analysis_id=info.analysis_id,
        model=config.OPENAI_CHAT_MODEL if reply.usage.calls else None,
        prompt_tokens=reply.usage.prompt_tokens,
        completion_tokens=reply.usage.completion_tokens,
        latency_ms=int((_now() - answer.created_at).total_seconds() * 1000),
    )
    if saved and "crisis" in r.safety_types:
        await repo.set_safety_mode(s.id, _next_midnight())


# 약 두 개짜리 경고 (⑤ 먹는 약끼리 묻는 질문, 노인주의, 연령금기, 용량, 여러 약 복용은 약 하나짜리라 뺌)
PAIR_WARNINGS = ("interaction", "duplicate_ingredient", "duplicate_efficacy")


def _item_name(it: PrescriptionItem) -> str:
    return display_name(it.drug.item_name) if it.drug else it.raw_name  # 분석 화면(R-4)과 같은 이름


async def _pair_warnings(aid: int) -> tuple[list[PairWarning], list[PairWarning]]:
    """(약 두 개짜리 경고, 약 하나짜리 경고). 처방을 지워 약이 빠진 경고는 뺌"""
    rows = await AnalysisWarning.filter(analysis_id=aid).order_by("id").prefetch_related("item_a__drug", "item_b__drug")
    pairs = [
        PairWarning(w.id, (_item_name(w.item_a), _item_name(w.item_b)), w.summary or "")
        for w in rows
        if w.warning_type in PAIR_WARNINGS and w.item_a and w.item_b
    ]
    # 여러 약 복용(polypharmacy)은 약 여러 개에 대한 경고라 이름 없이 (#195 채연 리뷰)
    singles = [
        PairWarning(w.id, () if w.warning_type == "polypharmacy" else (_item_name(w.item_a),), w.summary or "")
        for w in rows
        if w.warning_type not in PAIR_WARNINGS and (w.item_a or w.warning_type == "polypharmacy")
    ]
    return pairs, singles


# ── 고정 정보 (설계 메모 7-11) ─────────────────────────────────────────────────────────────
async def _analysis_for(user: User, s: ChatSession) -> int | None:
    """후보 셋 중 가장 나중에 생긴 것의 분석을 씀 (#159, #162 채연 리뷰). 시각이 같으면 앞의 것.
    가장 최근에 붙은 맥락 카드(붙은 때), 대화에 적힌 분석(대화를 연 때와 그 분석이 끝난 때 중 늦은 쪽),
    가장 최근에 끝난 완료 분석(끝난 때). 그래서 같은 날 새 분석을 하면 다음 질문부터 새 분석을 쓰고,
    결과 화면에서 예전 기록으로 연 대화는 그 기록을 씀. 지워진 분석과 남의 분석은 건너뜀.
    최근 완료 분석을 쓰면 대화에 적음 (R-8로 같이 지워지게, #100). 완료 분석이 없으면 일반 질문 모드 (명세서 H-1)"""
    picks: list[tuple[datetime, int]] = []
    card = await repo.last_card(s)
    card_aid = card.context_card.get("analysisId") if card else None
    if card and card_aid and await Analysis.exists(id=card_aid, user=user):
        picks.append((card.created_at, int(card_aid)))
    current = await Analysis.get_or_none(id=s.analysis_id, user=user) if s.analysis_id else None
    if current:
        picks.append((max(s.created_at, current.finished_at or s.created_at), current.id))
    latest = (
        await Analysis.filter(user=user, status=AnalysisStatus.DONE, finished_at__not_isnull=True)
        .order_by("-finished_at", "-id")
        .first()
    )
    if latest:
        picks.append((latest.finished_at, latest.id))
    if not picks:
        return None
    when, aid = max(picks, key=lambda p: p[0])  # max는 같은 값이면 앞의 것을 돌려줌
    if latest and (when, aid) == (latest.finished_at, latest.id) and aid != s.analysis_id:
        await ChatSession.filter(id=s.id).update(analysis_id=aid)
        s.analysis_id = aid
    return aid


async def _card_focus(info: FixedInfo, before: list[ChatMessage]) -> tuple[str | None, int | None]:
    """마지막 맥락 카드가 가리키는 것: 약 카드면 그 약 이름("이 약 물어보기", RG-04), 경고 카드면 그 경고 번호(RG-03).
    고정 정보를 가져온 분석의 카드일 때만 쓰고, 카드 뒤에 카드에 없는 약을 물었으면 그 약 이야기일 수 있어 쓰지 않음
    (11/2 서버 E2E)"""
    card = next((m for m in reversed(before) if m.context_card), None)
    ctx = (card.context_card or {}).get("context") if card else None
    if not card or not ctx or card.context_card.get("analysisId") != info.analysis_id:
        return None, None
    name: str | None = None
    if ctx.get("type") == "drug":
        rx_ids = await AnalysisPrescription.filter(analysis_id=info.analysis_id).values_list(
            "prescription_id", flat=True
        )
        it = await PrescriptionItem.get_or_none(id=ctx.get("id"), prescription_id__in=list(rx_ids)).prefetch_related(
            "drug"
        )
        if it is None or it.drug is None:
            return None, None
        name = display_name(it.drug.item_name)
        on_card: tuple[str, ...] = (name,)
    elif ctx.get("type") == "warning":
        on_card = next((w.names for w in info.pair_warnings if w.id == ctx.get("id")), ())
    else:
        return None, None
    for m in before:
        if m.id > card.id and m.role == MessageRole.USER and m.content:
            d = find_drug(m.content, info.drugs)
            if d and d.name not in on_card:
                return None, None
    return (name, None) if name else (None, ctx.get("id"))


async def fixed_info(user: User, s: ChatSession) -> FixedInfo:
    """민감정보 동의가 있을 때만 나이, 내 약과 질환을 넣음. 없으면 일반 정보만 (명세서 H-1, 설계 메모 0-1 항목 5)"""
    if not await has_health_consent(user):
        return FixedInfo(age=None)  # 나이도 넣지 않음 (일반 정보만, 10/22)
    info = FixedInfo(age=_now().year - user.birth_year)
    aid = await _analysis_for(user, s)
    if aid is None:
        return info
    info.analysis_id = aid
    info.pair_warnings, info.other_warnings = await _pair_warnings(aid)

    rx_ids = await AnalysisPrescription.filter(analysis_id=aid).values_list("prescription_id", flat=True)
    items = (
        await PrescriptionItem.filter(prescription_id__in=list(rx_ids), match_status__in=USABLE, drug_id__isnull=False)
        .order_by("prescription_id", "id")
        .prefetch_related("drug")
    )
    drugs = [(it, it.drug) for it in items if it.drug is not None]
    codes = list(dict.fromkeys(d.edi_code for _, d in drugs))
    approved = await DrugGuide.filter(edi_code__in=codes, review_status=ReviewStatus.APPROVED)
    purpose = {g.edi_code: (g.content or {}).get("purpose") or "" for g in approved}
    try:
        ingredient = safety.ingredient_names(codes)
    except safety.SafetyDbMissingError:  # 점검 DB가 없어도 답은 만듦 (성분만 비움)
        ingredient = {}
    seen: set[str] = set()
    for it, drug in drugs:
        code = drug.edi_code
        if code in seen:
            continue
        seen.add(code)
        info.drugs.append(
            UserDrug(
                name=display_name(drug.item_name),
                ingredient=ingredient.get(code) or "",
                purpose=purpose.get(code, ""),
                how=medication.how_to_take(it, drug) or "",
                code=code,
                class_code=drug.class_code or "",
            )
        )

    disease_codes = await AnalysisDisease.filter(analysis_id=aid).order_by("id").values_list("disease_id", flat=True)
    for kcd in disease_codes:
        d = lifestyle.disease_of(str(kcd))
        if d and d["id"] not in info.disease_ids:
            info.disease_ids.append(d["id"])
            info.diseases.append(d["name"])
    return info
