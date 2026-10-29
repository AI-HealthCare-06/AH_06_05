"""피처 3 챗봇 서비스 (API H-1 ~ H-8, #100)

질문 보내기(H-3): 1층과 문맥 파악(AI 없음)을 저장 전에 보고, 막을 질문이면 원문 없이 긴급 답 줄을 바로 만듦.
아니면 질문 줄과 만드는 중(generating) 답 줄을 만들고 202를 돌려준 뒤, 뒤에서 답을 끝까지 만들어 한 번에 저장함.
지금은 FastAPI 백그라운드 작업으로 돌리고, 10/26 워커 이전 뒤 arq로 옮김 (#118).
질문 원문은 로그에 남기지 않음.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

from starlette import status

from app.core import config
from app.core.errors import AppError
from app.models.analysis import (
    Analysis,
    AnalysisDisease,
    AnalysisPrescription,
    AnalysisWarning,
    DrugGuide,
    ReviewStatus,
)
from app.models.chat import AnswerType, ChatMessage, ChatSession, MessageStatus
from app.models.ocr import MatchStatus, PrescriptionItem
from app.models.users import User
from app.repositories.chat import ChatRepository
from app.services import safety
from app.services.chatbot import pipeline
from app.services.chatbot.context import FixedInfo, PairWarning, UserDrug
from app.services.chatbot.evidence import JOB_LIMIT_SEC
from app.services.chatbot.llm import make_client
from app.services.chatbot.pipeline import Reply, Route
from app.services.drug_names import base_name
from app.services.guide import lifestyle, medication
from app.services.prescriptions import has_health_consent

logger = logging.getLogger(__name__)
repo = ChatRepository()

# 답 만들기 전체를 이 안에서 끊음. 분류와 답 만들기를 차례로 부르면 15초 + 15초로 넘을 수 있어서 (10/22)
ANSWER_TIMEOUT_SEC = JOB_LIMIT_SEC
STALE_SEC = 30  # 만드는 중으로 이보다 오래된 답 줄은 다시 시도 때 지우고 새로 만듦 (명세서 H-3)
USABLE = (MatchStatus.AUTO, MatchStatus.USER_CONFIRMED)
DRUG_SOURCE = "식약처 의약품 허가정보"  # 근거 번호 D:<약코드>:S12 (허가정보 문장)


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
    until = s.safety_mode_until if s and s.safety_mode_until and s.safety_mode_until > _now() else None
    return {
        "sessionId": s.id if s else None,
        "hasHistory": await repo.has_session(user),
        "safetyModeUntil": until.isoformat() if until else None,
    }


async def delete_session(user: User, session_id: int) -> None:
    await repo.delete_session(await _session(user, session_id))


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
    for key, value in (("contextCard", m.context_card), ("safetyCard", m.safety_card), ("safety", m.safety)):
        if value:
            row[key] = value
    row["createdAt"] = m.created_at.isoformat()
    return row


async def messages(user: User, session_id: int) -> dict[str, Any]:
    return {"items": [_item(m) for m in await repo.messages(await _session(user, session_id))]}


# ── H-7 맥락 카드 ──────────────────────────────────────────────────────────────────────────
async def add_context(
    user: User, session_id: int, analysis_id: int, context: dict[str, Any] | None, client_request_id: str
) -> None:
    """같은 clientRequestId면 카드 줄을 새로 만들지 않음. firstMessage는 아직 없음 (#116)"""
    s = await _session(user, session_id)
    await _check_analysis(user, analysis_id)
    if await repo.get_by_request(s, client_request_id):
        return
    card: dict[str, Any] = {"analysisId": analysis_id}
    if context:
        card["context"] = context
    await repo.create_card(s, client_request_id, card)


# ── H-3 질문 보내기 ────────────────────────────────────────────────────────────────────────
def _safety(r: Route) -> dict[str, Any]:
    """원문 없이 걸린 갈래와 규칙 이름만 (명세서 H-3 safety, 설계 메모 SafetyInfo.rule은 글자 하나라 쉼표로 이음)"""
    return {"types": r.safety_types, "overdose": r.overdose, "rule": ",".join(r.safety_rules)}


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

    blocked, _ = pipeline.first_layer(content, emergency_dismissed)
    if blocked:  # 1층이 잡고 문맥 파악이 풀지 않음: 원문을 저장하지 않고 긴급 답을 바로 (설계 메모 4-6)
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
    answer = await repo.create_question_and_answer(s, content, client_request_id, status=MessageStatus.GENERATING)
    return answer.id, True


async def run_pipeline(
    question: str, info: FixedInfo, history: list[dict[str, str]], emergency_dismissed: bool = False
) -> Reply:
    """답 만들기 (OpenAI). 시험에서는 가짜로 바꿈"""
    return await pipeline.answer(question, info, history, make_client(), emergency_dismissed=emergency_dismissed)


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
        titles += [DRUG_SOURCE] if kind == "D" else _fact_sources(i) if kind == "F" else []
    return [{"title": t} for t in dict.fromkeys(titles)]


def _history(rows: list[ChatMessage]) -> list[dict[str, str]]:
    """빈 글 줄(1층이 잡은 질문, 긴급 답, 맥락 카드)은 대화 기억에 넣지 않음.
    범위 밖으로 걸러진 질문과 그 답도 뺌. 앞 대화가 다음 답의 노이즈가 됨 (5회차 멘토링 시연, #99)"""
    skip = {m.reply_to_id for m in rows if m.route_kind == "out_of_scope"}
    return [
        {"role": m.role.value, "content": m.content}
        for m in rows
        if m.content and m.route_kind != "out_of_scope" and m.id not in skip
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
        history = _history(await repo.done_messages_before(s.id, question.id))
        reply: Reply | None = await asyncio.wait_for(
            run_pipeline(question.content, info, history, emergency_dismissed), ANSWER_TIMEOUT_SEC
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
        route_kind=r.kind,
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
    return base_name(it.drug.item_name) if it.drug else it.raw_name  # 분석 화면(R-4)과 같은 이름


async def _pair_warnings(aid: int) -> list[PairWarning]:
    rows = (
        await AnalysisWarning.filter(analysis_id=aid, warning_type__in=PAIR_WARNINGS)
        .order_by("id")
        .prefetch_related("item_a__drug", "item_b__drug")
    )
    return [
        PairWarning(w.id, (_item_name(w.item_a), _item_name(w.item_b)), w.summary or "")
        for w in rows
        if w.item_a and w.item_b  # 처방을 지워 약이 빠진 경고는 뺌
    ]


# ── 고정 정보 (설계 메모 7-11) ─────────────────────────────────────────────────────────────
async def _analysis_for(user: User, s: ChatSession) -> int | None:
    """가장 최근에 붙은 맥락 카드의 분석, 없으면 H-1 analysisId. 지워진 분석은 건너뜀"""
    for aid in (await repo.last_card_analysis(s), s.analysis_id):
        if aid and await Analysis.exists(id=aid, user=user):
            return int(aid)
    return None


async def fixed_info(user: User, s: ChatSession) -> FixedInfo:
    """민감정보 동의가 있을 때만 나이, 내 약과 질환을 넣음. 없으면 일반 정보만 (명세서 H-1, 설계 메모 0-1 항목 5)"""
    if not await has_health_consent(user):
        return FixedInfo(age=None)  # 나이도 넣지 않음 (일반 정보만, 10/22)
    info = FixedInfo(age=_now().year - user.birth_year)
    aid = await _analysis_for(user, s)
    if aid is None:
        return info
    info.analysis_id = aid
    info.pair_warnings = await _pair_warnings(aid)

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
                name=base_name(drug.item_name),
                ingredient=ingredient.get(code) or "",
                purpose=purpose.get(code, ""),
                how=medication.how_to_take(it, drug) or "",
                code=code,
            )
        )

    disease_codes = await AnalysisDisease.filter(analysis_id=aid).order_by("id").values_list("disease_id", flat=True)
    for kcd in disease_codes:
        d = lifestyle.disease_of(str(kcd))
        if d and d["id"] not in info.disease_ids:
            info.disease_ids.append(d["id"])
            info.diseases.append(d["name"])
    return info
