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
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field, replace
from typing import Any

from app.services.chatbot import context_check, evidence, safety_rules
from app.services.chatbot.answer import REFER, SPEECH, clean_text, out_of_scope, write
from app.services.chatbot.classify import (
    asks_food_to_avoid,
    asks_this_analysis,
    check_classification,
    classify,
    classify_message,
)
from app.services.chatbot.context import FixedInfo, PairWarning, find_drug, recent, resolve_ordinal
from app.services.chatbot.guard import guard
from app.services.chatbot.llm import ChatClient, LLMError, Usage
from app.services.rag.gate import Verdicts
from app.services.rag.pipeline import SearchResult
from app.services.rag.pipeline import search as rag_search

CLARIFY_GUESS = "앞에서 말씀하신 약이 어떤 약인지 다시 알려 주시겠어요?"  # 기억 밖의 약을 단정하지 않음
CLARIFY_DEFAULT = "어떤 약을 말씀하시는지 알려 주시겠어요?"
# 맥락 카드의 약을 가리키는 말 ("이 약은 언제 먹어요?", "이거 저녁에 먹어도 돼요?")
_THIS_DRUG = re.compile(r"이\s*약(?![속국간])|이거|이것")
# 분석 칩에 근거로 답하면 AI가 허가정보를 분석 결론처럼 말함 (10/27 측정 3번 중 3번). 분석 결과는 분석 화면이 보여 줌.
# 점검할 약이 없을 때만 이 안내. 경고가 있으면 ⑤ 점검 결과로, 없으면 아래 NO_WARNINGS로 답함 (11/2 멘토 피드백 "오히려 모른다",
# 10/26의 "경고가 없다고 말하지 않음" 결정을 바꿈. 대신 무엇을 점검했고 무엇은 점검하지 않는지 같이 적음). 화면 문구라 신규 임시
ANALYSIS_GUIDE = "이번 분석에서 가장 조심할 점은 분석 결과 화면에서 확인해 주세요. 궁금한 점은 약사에게 확인해 주세요."
NO_WARNINGS_CHECKS = "함께 먹으면 안 되는 약, 같은 성분이나 효과가 겹치는 약, 어르신이 조심해야 하는 약, 나이에 맞지 않는 약, 하루 최대량"
NO_WARNINGS_TAIL = "음식이나 술, 처방에 없는 약은 점검하지 않아요.\n\n약마다 주의할 점은 분석 결과의 복약 안내에서 볼 수 있어요. 약사에게 확인해 주세요."


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
    clarify_chips: list[str] = field(default_factory=list)  # 되물을 때 예상 답 칩 (분류가 만듦, 11/2)
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


_VERDICT_NAMES = {"ENOUGH", "PARTIAL", "INSUFFICIENT", "FULL", "NONE"}


def _verdicts(v: Verdicts | None) -> str | None:
    """판정 세 가지를 로그 한 줄로. 판정 AI가 돌려준 값이라 알려진 이름만 남기고 나머지는 ? (글이 섞이지 않게)"""
    if v is None:
        return None
    a, b, c = (x if x in _VERDICT_NAMES else "?" for x in (v.a, v.b, v.c))
    return f"a={a} b={b}/{'direct' if v.b_direct else 'indirect'} c={c}"


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
    if not resolved and info.focus_drug and _THIS_DRUG.search(question) and not find_drug(question, info.drugs):
        resolved = info.focus_drug  # "이 약"은 맥락 카드의 약. 다른 약 이름이 있으면 분류대로
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
        # 칩은 분류가 만든 되묻는 문장을 그대로 쓸 때만. 고정 문구로 바꾸면 칩이 그 문장과 맞지 않을 수 있음
        chips = _clarify_chips(cls.get("clarify_options")) if follow == cls["clarify_question"] else []
        return Route(
            kind="clarify",
            context_release=release,
            classification=cls,
            clarify_question=follow,
            clarify_chips=chips,
            usage=usage,
        )
    if cls["category"] == "clarify":
        cls["category"] = "medication"  # 대상 약을 찾았으면 되묻지 않음
    return Route(kind=cls["category"], context_release=release, classification=cls, usage=usage)


CHIP_MAX, CHIP_LEN = 3, 15  # 되물음 예상 답 칩 수와 글자 수 (시작값, 11/2)

# drugMatch: 질문의 약 이름이 내 약에 없으면 O-4와 같은 이름 맞추기로 찾음 (명세서 O-4 챗봇 줄, #116, 11/2).
# 후보가 여럿이면 후보 이름을 칩으로 되묻고, 정확히 하나면 그 약 범위로 근거를 찾음. 못 찾으면 되묻지 않고 지금처럼 진행
# ("혈압약"처럼 쓰임으로 말한 약을 되물을 수 있어서, 시연 뒤 실제 분류로 재서 정함). 화면 문구라 신규 임시
DRUG_PICK = "말씀하신 약이 아래 중 하나인가요? 맞는 약을 골라 주세요. 목록에 없으면 약봉투에 적힌 이름을 알려 주세요."
DrugMatch = Callable[[str], Awaitable[dict[str, Any] | None]]  # O-4 search_drugs와 같은 응답 { status, items }
_GENERIC_DRUG = re.compile(
    r"(약|제|주사|연고|시럽)$"
)  # 혈압약, 진통제처럼 쓰임이나 종류로 말한 것은 이름 맞추기 대상이 아님


async def no_match(_: str) -> None:
    return None


def _drug_pick(dm: dict[str, Any] | None) -> list[str] | None:
    """후보가 여럿이면 되물을 때 보여 줄 후보 이름 칩, 아니면 None"""
    items = (dm or {}).get("items") or []
    if dm and dm.get("status") == "candidates" and items:
        return [i["itemName"] for i in items[:CHIP_MAX]]
    return None


def _drug_scope(dm: dict[str, Any] | None) -> tuple[dict[str, Any] | None, list[str] | None]:
    """정확히 하나로 맞았으면 (답 줄에 실을 drugMatch, 근거 검색 약 코드), 아니면 (None, None)"""
    items = (dm or {}).get("items") or []
    if dm and dm.get("status") == "matched" and items and items[0].get("ediCode"):
        return dm, [items[0]["ediCode"]]
    return None, None


def _needs_lookup(cls: dict[str, Any], question: str, info: FixedInfo, kind: str) -> bool:
    target = cls.get("target_drug") or ""
    if len(target) < 2 or cls.get("target_source") != "question" or kind not in ("medication", "refer"):
        return False
    return not _GENERIC_DRUG.search(target) and find_drug(question, info.drugs) is None


def _clarify_chips(options: Any) -> list[str]:
    """분류가 만든 예상 답을 칩으로. 글 규칙(clean_text)을 거치고, 빈 것과 긴 것과 겹치는 것은 뺌"""
    if not isinstance(options, list):
        return []
    out: list[str] = []
    for o in options:
        text = clean_text(o).strip() if isinstance(o, str) else ""
        if text and len(text) <= CHIP_LEN and text not in out:
            out.append(text)
    return out[:CHIP_MAX]


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
    # 판정에서 막혔을 때(insufficient, risk_blocked) 어느 판정이 막았는지 로그용 요약 (#124 채연 리뷰)
    evidence_verdicts: str | None = None
    chips: list[str] = field(default_factory=list)  # 되물음(clarify) 아래 예상 답 칩 (명세서 H-2 chips, 11/2)
    drug_match: dict[str, Any] | None = None  # 질문의 약 이름 맞추기 결과 { status, items } (명세서 H-2 drugMatch, O-4)


# ⑤ 점검 결과로 답할 때의 앞뒤 문장 (화면 문구, 신규 임시, 10/26 수인 결정. 와이어프레임에는 나중에 맞춤)
SAFETY_HEAD = "분석에서 확인된, 같이 먹을 때 주의할 점이에요."
SAFETY_TAIL = "위 내용은 분석 결과에서 자세히 볼 수 있어요. 약사에게 확인해 주세요."


# 술, 음식, 영양제처럼 점검(DUR)에 없는 것을 같이 묻는 질문. 약끼리 경고만 나가면 술은 괜찮다고 읽힐 수 있어 ⑤를 건너뜀.
# 분류가 먹는 약끼리로 흔들림 ("다이아벡스랑 술 같이 마셔도 돼요?" 10번 중 3번, #134 리뷰 2번). "수술"의 "술"은 빼고 (10/27 수인 결정)
_NOT_CHECKED = re.compile(
    r"(?<![수기])술|음주|맥주|소주|와인|막걸리|양주|음식|식사|주스|자몽|커피|우유|녹차|영양제|한약|건강식품"
)


def _no_warnings(info: FixedInfo) -> str:
    """분석 칩에 경고가 하나도 없을 때. 점검한 약 이름(4개까지, 넘으면 "등")과 점검 기준, 점검하지 않는 것을 적음 (11/2)"""
    names = [d.name for d in info.drugs]
    listed = ", ".join(names[:4]) + (" 등" if len(names) > 4 else "")
    return (
        f"이번 분석에서는 {listed} {len(names)}개를 점검했어요.\n\n"
        f"{NO_WARNINGS_CHECKS} 기준에 걸린 항목은 없었어요. {NO_WARNINGS_TAIL}"
    )


def _check_reply(question: str, cls: dict[str, Any], info: FixedInfo, r: Route, usage: Usage) -> Reply | None:
    """⑤ 먹는 약끼리 같이 먹어도 되는지 물으면 분석의 경고를 그대로 보여 주고 AI가 다시 판단하지 않음 (설계 메모 7-12, NFR-032).
    약 두 개짜리 경고가 없으면 None (분석 칩은 _analysis_reply, 나머지는 근거 검색)"""
    checked_only = not _NOT_CHECKED.search(question)
    if not (cls.get("about_user_drugs") and r.kind in ("medication", "refer") and info.pair_warnings and checked_only):
        return None
    # 경고 카드로 연 대화는 그 경고만. 분석 전체를 물으면(분석 칩) 다 보여 줌 (11/2 서버 E2E)
    shown = [w for w in info.pair_warnings if w.id == info.focus_warning and not asks_this_analysis(question)]
    # 분석 전체를 물으면 약 하나짜리 경고(노인주의 등)도 같이 (11/2 멘토 피드백)
    shown = shown or info.pair_warnings + (info.other_warnings if asks_this_analysis(question) else [])
    card = {"analysisId": info.analysis_id, "warningIds": [w.id for w in shown]}
    # 끊거나 바꾸려는 질문(next_visit)과 증상(soon)은 끝 문장을 그 상담 문구로. 약을 끊는 건 의사 판단 (#134 리뷰 1번)
    kind = cls.get("refer_kind") if r.kind == "refer" else None
    if kind in ("next_visit", "soon"):
        return Reply("refer", _check_result(shown, REFER[kind]), r, usage=usage, safety_card=card)
    return Reply("normal", _check_result(shown), r, usage=usage, safety_card=card)


def _analysis_reply(info: FixedInfo, r: Route, usage: Usage) -> Reply:
    """분석 칩인데 약 두 개짜리 경고가 없을 때. 약 하나짜리 경고(노인주의 등)가 있으면 ⑤와 같은 모양으로 답하고 카드를 붙임.
    경고가 없으면 점검한 약과 기준을 적음. 점검한 약이 없으면 화면 안내 (11/2 멘토 피드백)"""
    if info.other_warnings:
        card = {"analysisId": info.analysis_id, "warningIds": [w.id for w in info.other_warnings]}
        return Reply("normal", _check_result(info.other_warnings), r, usage=usage, safety_card=card)
    return Reply("normal", _no_warnings(info) if info.drugs else ANALYSIS_GUIDE, r, usage=usage)


def _check_result(warnings: list[PairWarning], tail: str = SAFETY_TAIL) -> str:
    """경고마다 "약A, 약B: 점검 문장" 한 줄. 약 이름 뒤 조사는 괄호로 끝나는 이름이 많아 쉼표로 이음 (10/26 수인 결정).
    경고 사이와 끝 문장 앞은 빈 줄. 좁은 화면에서 한 경고가 여러 줄로 접히면 다음 경고나 끝 문장과 구분되지 않음.
    끝 문장의 "위 내용은"은 경고 전체에 대한 말임을 글로도 밝힘 (읽어주기). 머리 문장은 목록의 제목이라 붙임 (10/27 수인 결정)"""
    lines = "\n\n".join(f"{', '.join(w.names)}: {w.summary}" for w in warnings)
    return f"{SAFETY_HEAD}\n{lines}\n\n{tail}"


# 음식, 술, 식사를 말하는 허가정보 문장. "수술", "기술"의 술은 아님
_FOOD_WORDS = re.compile(r"음식|식사|식품|식이|공복|(?<![수기시])술|음주|알코올|자몽|우유|커피|카페인|녹차|주스|섭취")


def _food_only(found: SearchResult) -> SearchResult:
    """피할 음식을 물으면 허가정보 근거는 음식 말이 든 문장만 남김. 약끼리 상호작용 문장("CYP3A4 억제제와 병용")을
    답 AI가 음식 답처럼 옮김 (11/2 서버 E2E, 로컬 재현 4번 중 4번). 팩트표 근거는 그대로. 다 빠지면 근거 없음"""
    keep = [e for e in found.evidence if e.source != "drug_permit" or _FOOD_WORDS.search(f"{e.heading} {e.text}")]
    return replace(found, evidence=keep, reason=found.reason or (None if keep else "no_food_evidence"))


async def answer(
    question: str,
    info: FixedInfo,
    history: list[dict[str, str]],
    client: ChatClient,
    summary: str | None = None,
    search: evidence.Search = rag_search,
    emergency_dismissed: bool = False,
    match: DrugMatch = no_match,
) -> Reply:
    started = time.perf_counter()
    r = await route(question, info, history, client, summary, emergency_dismissed)
    usage = Usage()
    usage.add(r.usage)
    # 1층과 2층이 막지 않은 말 이상은 분류와 상관없이 고정 안내. 범위 밖 사과, 약 되묻기, "며칠 안에 진료"로 끝나던 것 (#132 채연 리뷰)
    if r.kind in ("clarify", "medication", "lifestyle", "refer", "out_of_scope") and safety_rules.odd_speech(question):
        return Reply("refer", SPEECH, r, usage=usage)
    if r.kind == "clarify":
        return Reply("clarify", r.clarify_question, r, usage=usage, chips=r.clarify_chips)
    if r.kind not in ("medication", "lifestyle", "refer", "out_of_scope"):
        return Reply(r.kind, None, r, usage=usage)  # 긴급, 자해, 오류는 화면 고정 카드

    cls = r.classification or {}
    if (checked := _check_reply(question, cls, info, r, usage)) is not None:
        return checked
    if r.kind == "medication" and asks_this_analysis(question):
        return _analysis_reply(info, r, usage)
    if r.kind == "out_of_scope":
        # 범위 밖은 답 AI 없이 늘 같은 문구 (5회차 멘토링 시연, #99). 다음 질문의 대화 기억에서도 뺌 (chats._history)
        draft = out_of_scope(question, cls, info)
        return Reply(draft.answer_type, draft.content, r, usage=usage)
    return await _answer_from_evidence(question, cls, info, history, client, search, match, r, usage, started)


async def _answer_from_evidence(  # noqa: PLR0913
    question: str,
    cls: dict[str, Any],
    info: FixedInfo,
    history: list[dict[str, str]],
    client: ChatClient,
    search: evidence.Search,
    match: DrugMatch,
    r: Route,
    usage: Usage,
    started: float,
) -> Reply:
    """⑥ 근거 검색과 답 만들기. 앞에 drugMatch(내 약에 없는 약 이름 맞추기)"""
    # drugMatch: 내 약에 없는 약 이름이면 이름 맞추기. 후보가 여럿이면 후보 칩으로 되묻고, 하나면 그 약 범위로 근거를 찾음
    matched, codes = None, None
    if _needs_lookup(cls, question, info, r.kind):
        dm = await match(cls["target_drug"])
        if (ask := _drug_pick(dm)) is not None:
            return Reply("clarify", DRUG_PICK, r, usage=usage, chips=ask, drug_match=dm)
        matched, codes = _drug_scope(dm)
    found = await evidence.gather(question, cls, info, search, time.perf_counter() - started, codes)
    if asks_food_to_avoid(question):
        found = _food_only(found)
    past, first_turn = _turns(history)
    try:
        draft = await write(question, cls, info, past, first_turn, found, client, usage)
    except LLMError:
        return Reply("error", None, r, evidence_reason=found.reason if found else None, usage=usage)
    # 출력 가드레일에 걸렸으면 그 이유를 근거 없음 이유 자리에 (#124가 병합되면 대화 API가 메시지 번호와 같이 로그에 남김)
    reason = f"output_guard:{draft.blocked}" if draft.blocked else (found.reason if found else None)
    verdicts = _verdicts(found.verdicts) if found and found.reason in ("insufficient", "risk_blocked") else None
    return Reply(
        draft.answer_type,
        draft.content,
        r,
        draft.sources,
        reason,
        usage,
        evidence_verdicts=verdicts,
        drug_match=matched,
    )
