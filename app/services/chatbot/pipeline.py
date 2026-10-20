"""챗봇 답변 흐름 (#99). PR 1은 질문을 받아 갈래를 정하는 데까지.

순서: 1층 규칙(AI 없음) → 문맥 파악 → 2층 가드레일과 질문 분류를 동시에 → 갈래
- 1층에 걸리고 문맥 파악이 풀지 않으면 AI를 부르지 않고 긴급 안내(emergency) 또는 도움 연결(crisis)
- 문맥 파악이 풀었거나 1층에 걸리지 않으면 2층을 늘 거침
- 2층이 응답하지 않으면 답을 만들지 않고 답변 오류(error, 화면 E6). 1층만으로 답하면 2층에 넘긴 애매한 위기 표현을 아무도 못 잡음 (10/19 수인 결정)
- 2층이 위험이라고 하면 분류가 실패했어도 안내를 보여 줌

PR 2에서 더할 것: 약 이름 검색으로 되묻기, 제품 이름을 모르는 약("두통약") 되묻기, 허가정보로 음식 질문 보정, 근거 모으기, 답 만들기, 정리
결과에는 질문 원문을 담지 않는다 (설계 메모 7-2).
"""

import asyncio
from dataclasses import dataclass, field
from typing import Any

from app.services.chatbot import context_check, safety_rules
from app.services.chatbot.classify import check_classification, classify, classify_message
from app.services.chatbot.context import FixedInfo, recent, resolve_ordinal
from app.services.chatbot.guard import guard
from app.services.chatbot.llm import ChatClient, LLMError, Usage

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


def _safety(types: list[str], layer: int, rules: list[str], overdose: bool = False, **kw: Any) -> Route:
    return Route(kind=types[0], layer=layer, safety_types=types, overdose=overdose, safety_rules=rules, **kw)


async def route(
    question: str,
    info: FixedInfo,
    history: list[dict[str, str]],
    client: ChatClient,
    summary: str | None = None,
) -> Route:
    rule = safety_rules.check(question)
    release = context_check.looks_normal(question, rule)
    if rule.hit and release is None:
        return _safety(rule.types, 1, rule.rules, rule.overdose)

    past = recent(history)
    first_turn = len(history) // 2 - len(past) // 2 + 1
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
    if risk in ("emergency", "crisis"):
        return _safety([risk], 2, ["llm_guard"], context_release=release, usage=usage)
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
