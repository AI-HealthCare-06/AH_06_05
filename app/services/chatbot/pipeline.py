"""챗봇 답변 흐름 (#99). route()는 질문을 받아 갈래를 정하고, answer()는 그 뒤 근거 모으기와 답 만들기까지 (PR 2-1).

순서: 1층 규칙(AI 없음) → 문맥 파악 → 2층 가드레일과 질문 분류를 동시에 → 갈래
- 1층에 걸리고 문맥 파악이 풀지 않으면 AI를 부르지 않고 긴급 안내(emergency) 또는 도움 연결(crisis)
- 문맥 파악이 풀었거나 1층에 걸리지 않으면 2층을 늘 거침
- 2층이 응답하지 않으면 답을 만들지 않고 답변 오류(error, 화면 E6). 1층만으로 답하면 2층에 넘긴 애매한 위기 표현을 아무도 못 잡음 (10/19 수인 결정)
- 2층이 위험이라고 하면 분류가 실패했어도 안내를 보여 줌
- 2층은 과다 복용인지 알려 주지 않으므로 2층 응급은 [지금은 증상이 없어요] 칩을 늘 숨김 (#108 리뷰, 10/20 수인 결정)
- emergency_dismissed: [지금은 증상이 없어요] 뒤 다시 보낸 질문은 1층 응급 규칙과 2층 emergency를 건너뛰고 자해만 봄 (명세서 H-3, 10/22)

PR 2-2에서 더할 것: 약 이름 검색으로 되묻기, 제품 이름을 모르는 약("두통약") 되묻기, 허가정보로 음식 질문 보정, 사실 칸, 다시 만들기
결과에는 질문 원문을 담지 않는다 (설계 메모 7-2).
"""

import asyncio
import re
import time
from dataclasses import dataclass, field
from typing import Any

from app.services.chatbot import context_check, evidence, safety_rules
from app.services.chatbot.answer import REFER, write
from app.services.chatbot.classify import check_classification, classify, classify_message
from app.services.chatbot.context import FixedInfo, recent, resolve_ordinal
from app.services.chatbot.guard import guard
from app.services.chatbot.llm import ChatClient, LLMError, Usage
from app.services.rag.pipeline import search as rag_search

CLARIFY_GUESS = "앞에서 말씀하신 약이 어떤 약인지 다시 알려 주시겠어요?"  # 기억 밖의 약을 단정하지 않음
CLARIFY_DEFAULT = "어떤 약을 말씀하시는지 알려 주시겠어요?"


@dataclass
class Route:
    kind: str  # emergency, crisis, error, medication, lifestyle, refer, clarify, out_of_scope
    layer: int | None = None  # 위험을 잡은 층 (1: 규칙, 2: LLM)
    safety_types: list[str] = field(default_factory=list)  # 1층 동시 해당이면 ["emergency", "crisis"]
    overdose: bool = False  # True면 [지금은 증상이 없어요] 칩을 보여 주지 않음
    safety_rules: list[str] = field(default_factory=list)  # 걸린 규칙 이름 (원문 없음)
    context_release: str | None = None  # 1층에 걸렸지만 문맥 파악이 푼 이유 이름
    classification: dict[str, Any] | None = None
    clarify_question: str | None = None
    usage: Usage = field(default_factory=Usage)


def _turns(history: list[dict[str, str]]) -> tuple[list[dict[str, str]], int]:
    """최근 N번과 그 첫 차례 번호. 앞 차례 답이 없어 기록이 홀수 개여도 번호가 밀리지 않게 질문 수로 셈"""
    past = recent(history)
    return past, sum(m["role"] == "user" for m in history[: len(history) - len(past)]) + 1


def _safety(types: list[str], layer: int, rules: list[str], overdose: bool = False, **kw: Any) -> Route:
    return Route(kind=types[0], layer=layer, safety_types=types, overdose=overdose, safety_rules=rules, **kw)


def first_layer(question: str, emergency_dismissed: bool = False) -> tuple[Route | None, str | None]:
    """1층 규칙과 문맥 파악 (AI 없음). 막을 질문이면 긴급, 자해 갈래를, 아니면 None과 문맥 파악이 푼 이유를 돌려줌.
    질문을 저장하기 전에 서버가 먼저 부름 (명세서 H-3)"""
    rule = safety_rules.check(question)
    if emergency_dismissed:
        rule = safety_rules.crisis_only(rule)
    release = context_check.looks_normal(question, rule)
    if rule.hit and release is None:
        return _safety(rule.types, 1, rule.rules, rule.overdose), None
    return None, release


async def route(
    question: str,
    info: FixedInfo,
    history: list[dict[str, str]],
    client: ChatClient,
    summary: str | None = None,
    emergency_dismissed: bool = False,
) -> Route:
    blocked, release = first_layer(question, emergency_dismissed)
    if blocked:
        return blocked

    past, first_turn = _turns(history)
    resolved = resolve_ordinal(question, history, info.drugs)
    message = classify_message(question, info, past, first_turn, summary, resolved)

    guard_usage, classify_usage = Usage(), Usage()
    risk, cls = await asyncio.gather(
        guard(question, client, guard_usage),
        classify(message, client, classify_usage),
        return_exceptions=True,
    )
    usage = Usage()
    usage.add(guard_usage)
    usage.add(classify_usage)

    if isinstance(risk, BaseException):
        if not isinstance(risk, LLMError):
            raise risk
        return Route(kind="error", context_release=release, usage=usage)
    if risk == "crisis" or (risk == "emergency" and not emergency_dismissed):
        return _safety([risk], 2, ["llm_guard"], risk == "emergency", context_release=release, usage=usage)
    if isinstance(cls, BaseException):
        if not isinstance(cls, LLMError):
            raise cls
        return Route(kind="error", context_release=release, usage=usage)

    cls = check_classification(cls, question, info, past, summary, resolved)
    if cls["target_source"] == "guess" or (cls["category"] == "clarify" and not cls["target_drug"]):
        follow = CLARIFY_GUESS if cls["target_source"] == "guess" else (cls["clarify_question"] or CLARIFY_DEFAULT)
        return Route(kind="clarify", context_release=release, classification=cls, clarify_question=follow, usage=usage)
    if cls["category"] == "clarify":
        cls["category"] = "medication"  # 대상 약을 찾았으면 되묻지 않음
    return Route(kind=cls["category"], context_release=release, classification=cls, usage=usage)


@dataclass
class Reply:
    """답 하나. content는 화면에 보일 글 (긴급, 자해, 오류는 화면 고정 카드라 None)"""

    answer_type: str  # normal, partial, no_evidence, refer, clarify, emergency, crisis, error
    content: str | None
    route: Route
    sources: list[str] = field(default_factory=list)  # 답에 쓴 근거 번호
    # 근거 검색이 빈 목록일 때 이유 (rag.search reason), 출력 가드레일이면 output_guard:<종류>
    evidence_reason: str | None = None
    usage: Usage = field(default_factory=Usage)
    safety_card: dict[str, Any] | None = None  # ⑤ { analysisId, warningIds } (명세서 v1.5 초안 H-2, H-3)


# ⑤ 점검 결과로 답할 때의 앞뒤 문장 (화면 문구, 신규 임시, 10/26 수인 결정. 와이어프레임에는 나중에 맞춤)
SAFETY_HEAD = "분석에서 확인된, 같이 먹을 때 주의할 점이에요."
SAFETY_TAIL = "위 내용은 분석 결과에서 자세히 볼 수 있어요. 약사에게 확인해 주세요."


# 술, 음식, 영양제처럼 점검(DUR)에 없는 것을 같이 묻는 질문. 약끼리 경고만 나가면 술은 괜찮다고 읽힐 수 있어 ⑤를 건너뜀.
# 분류가 먹는 약끼리로 흔들림 ("다이아벡스랑 술 같이 마셔도 돼요?" 10번 중 3번, #134 리뷰 2번). "수술"의 "술"은 빼고 (10/27 수인 결정)
_NOT_CHECKED = re.compile(
    r"(?<![수기])술|음주|맥주|소주|와인|막걸리|양주|음식|식사|주스|자몽|커피|우유|녹차|영양제|한약|건강식품"
)


def _check_result(info: FixedInfo, tail: str = SAFETY_TAIL) -> str:
    """경고마다 "약A, 약B: 점검 문장" 한 줄. 약 이름 뒤 조사는 괄호로 끝나는 이름이 많아 쉼표로 이음 (10/26 수인 결정).
    경고 사이와 끝 문장 앞은 빈 줄. 좁은 화면에서 한 경고가 여러 줄로 접히면 다음 경고나 끝 문장과 구분되지 않음.
    끝 문장의 "위 내용은"은 경고 전체에 대한 말임을 글로도 밝힘 (읽어주기). 머리 문장은 목록의 제목이라 붙임 (10/27 수인 결정)"""
    warnings = "\n\n".join(f"{', '.join(w.names)}: {w.summary}" for w in info.pair_warnings)
    return f"{SAFETY_HEAD}\n{warnings}\n\n{tail}"


async def answer(
    question: str,
    info: FixedInfo,
    history: list[dict[str, str]],
    client: ChatClient,
    summary: str | None = None,
    search: evidence.Search = rag_search,
    emergency_dismissed: bool = False,
) -> Reply:
    started = time.perf_counter()
    r = await route(question, info, history, client, summary, emergency_dismissed)
    usage = Usage()
    usage.add(r.usage)
    if r.kind == "clarify":
        return Reply("clarify", r.clarify_question, r, usage=usage)
    if r.kind not in ("medication", "lifestyle", "refer", "out_of_scope"):
        return Reply(r.kind, None, r, usage=usage)  # 긴급, 자해, 오류는 화면 고정 카드

    cls = r.classification or {}
    # ⑤ 먹는 약끼리 같이 먹어도 되는지 물으면 분석의 경고를 그대로 보여 주고 AI가 다시 판단하지 않음 (설계 메모 7-12, NFR-032).
    # 경고가 없으면 "걸린 항목이 없어요"가 안전하다는 말로 읽힐 수 있어 지금처럼 근거 검색 (10/26 수인 결정)
    checked_only = not _NOT_CHECKED.search(question)
    if cls.get("about_user_drugs") and r.kind in ("medication", "refer") and info.pair_warnings and checked_only:
        card = {"analysisId": info.analysis_id, "warningIds": [w.id for w in info.pair_warnings]}
        # 끊거나 바꾸려는 질문(next_visit)과 증상(soon)은 끝 문장을 그 상담 문구로. 약을 끊는 건 의사 판단 (#134 리뷰 1번)
        kind = cls.get("refer_kind") if r.kind == "refer" else None
        if kind in ("next_visit", "soon"):
            return Reply("refer", _check_result(info, REFER[kind]), r, usage=usage, safety_card=card)
        return Reply("normal", _check_result(info), r, usage=usage, safety_card=card)
    found = None
    if r.kind != "out_of_scope":
        found = await evidence.gather(question, cls, info, search, time.perf_counter() - started)
    past, first_turn = _turns(history)
    try:
        draft = await write(question, cls, info, past, first_turn, found, client, usage)
    except LLMError:
        return Reply("error", None, r, evidence_reason=found.reason if found else None, usage=usage)
    # 출력 가드레일에 걸렸으면 그 이유를 근거 없음 이유 자리에 (#124가 병합되면 대화 API가 메시지 번호와 같이 로그에 남김)
    reason = f"output_guard:{draft.blocked}" if draft.blocked else (found.reason if found else None)
    return Reply(draft.answer_type, draft.content, r, draft.sources, reason, usage)
