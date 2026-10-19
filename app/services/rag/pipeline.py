"""근거 검색과 판정 (v7 고정 설정, docs/design/embedding.md 2장). 챗봇은 `search()` 하나만 부르면 된다.

순서: 앞단 규칙 -> 질문 재작성 -> 후보 모으기 -> LLM이 최대 8개 고르기 -> 소항목 묶음으로 넓히기
      -> 판정 A, B, C(동시에) -> 다수결과 위험주제 규칙 -> 통과하면 근거, 아니면 빈 목록과 이유.

돌려주는 `reason` (목록이 빌 때만): no_code(약도 질환도 없음), no_candidate(그 약과 질환의 조각이 없음),
no_selection(고른 글이 없음), insufficient(판정 다수결 통과 못 함), risk_blocked(위험주제인데 완전 통과가 아님),
llm_error(OpenAI 호출 실패, 안전 쪽으로 빈 목록), timeout(`budget_sec`을 넘김, 안전 쪽으로 빈 목록).
챗봇은 reason이 있으면 no_evidence로 이어가면 된다.

시간 인자(모두 선택, 안 넣으면 지금 동작 그대로): `timeout_sec`은 OpenAI 호출 한 번의 제한 시간, `max_attempts`는 한 호출의
다시 시도 포함 최대 횟수, `budget_sec`은 search() 전체 제한 시간이다. 단계가 차례로 이어져서 앞의 둘만으로는 전체 시간이 정해지지
않으므로 챗봇 작업 제한(25초)에 맞추려면 `budget_sec`을 쓴다.

돌려주는 `coverage` (챗봇이 답, 부분 답, 확인이 어렵다 중에 고르는 기준): full(완전), partial(부분), none(없음).
판정 세 개(A, B, C) 중 둘 이상이 "충분" 쪽이면 full, 통과했지만 그렇지 않으면 partial, 통과 못 했거나 목록이 비면 none.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field

from app.services.rag import chunks as store
from app.services.rag import gate, prompts
from app.services.rag.chunks import Chunk
from app.services.rag.llm import LLM, LLMError, OpenAIClient

logger = logging.getLogger(__name__)

SCOPE_ALL_MAX = 90  # 범위 안 조각이 이 이하이면 전부를 후보로 삼는다
TOP_N = 30  # 넘으면 4가지 순위에서 각각 상위 이만큼
MAX_PICK = 8  # LLM이 고르는 최대 개수 (Top-K를 대신함)
SELECT_SHOW_MAX = 300  # 고르기 프롬프트에서 후보 글 한 조각의 최대 글자 수


@dataclass(frozen=True)
class Evidence:
    sentence_id: str  # 출처 번호 (허가정보 문장 번호 D:<약코드>:S12 형식, 팩트표는 F:...)
    source: str  # drug_permit | lifestyle_fact | cross_rule
    drug_code: str | None
    disease_code: str | None
    section: str | None  # E 효능효과, S 주의사항, P 용법용량
    heading: str
    text: str


@dataclass
class SearchResult:
    evidence: list[Evidence] = field(default_factory=list)
    reason: str | None = None
    rewritten: str | None = None
    verdicts: gate.Verdicts | None = None
    seconds: dict[str, float] = field(default_factory=dict)  # 단계별 걸린 시간 (Locust 측정용 기록)

    @property
    def coverage(self) -> str:
        """full(완전) / partial(부분) / none(없음). 새 판정을 만드는 것이 아니라 이미 낸 판정 세 개를 하나로 줄인 것"""
        if not self.evidence or self.verdicts is None:
            return "none"
        return "full" if sum(self.verdicts.fulls) >= 2 else "partial"


_SOURCE = {"drug": "drug_permit", "fact": "lifestyle_fact", "cross": "cross_rule"}


def to_evidence(c: Chunk) -> Evidence:
    return Evidence(c.chunk_id, _SOURCE[c.kind], c.drug_code, c.disease_code, c.section, c.heading, c.content)


def _asker_info(drugs: list[str], diseases: list[str], names: dict[str, str]) -> str:
    """질문자 정보 한 줄 (v6_run.info와 같은 모양)"""
    parts = []
    if drugs:
        parts.append("먹는 약 " + ", ".join(names.get(d, d) for d in drugs))
    if diseases:
        parts.append("질환 " + ", ".join(diseases))
    return "; ".join(parts) or "없음"


async def rewrite_question(llm: LLM, question: str, drug_labels: list[str], diseases: list[str]) -> str:
    labels = [prompts.DISEASE_LABELS.get(d, d) for d in diseases]
    text = (
        prompts.REWRITE_PROMPT
        + f"질문: {question}\n약: {', '.join(drug_labels) or '없음'}\n질환: {', '.join(labels) or '없음'}"
    )
    return (await llm.complete(text)).replace("\n", " ").replace("\t", " ")


async def gather_candidates(
    scope: list[Chunk],
    drugs: list[str],
    diseases: list[str],
    question_vec: list[float],
    rewrite_vec: list[float],
    question: str,
    rewritten: str,
) -> list[Chunk]:
    """후보 목록 (v7_run.cands2). 범위가 작으면 전부, 아니면 임베딩 2개와 글자 조각 2개 순위의 상위를 합친다"""
    if len(scope) <= SCOPE_ALL_MAX:
        return scope
    rankings = await asyncio.gather(
        store.rank_by_embedding(drugs, diseases, question_vec, TOP_N),
        store.rank_by_trgm(drugs, diseases, question, TOP_N),
        store.rank_by_embedding(drugs, diseases, rewrite_vec, TOP_N),
        store.rank_by_trgm(drugs, diseases, rewritten, TOP_N),
    )
    by_id = {c.chunk_id: c for c in scope}
    out: list[Chunk] = []
    seen: set[str] = set()
    for ids in rankings:
        for cid in ids:
            if cid in by_id and cid not in seen:
                seen.add(cid)
                out.append(by_id[cid])
    return out


def selection_prompt(question: str, rewritten: str, info: str, candidates: list[Chunk]) -> str:
    return (
        prompts.SELECT_PROMPT
        + f"질문: {question}\n(의학 용어로 다시 쓴 질문: {rewritten})\n(질문자 정보: {info})\n후보 글:\n"
        + "\n".join(f"[{i}] {store.show(c)[:SELECT_SHOW_MAX]}" for i, c in enumerate(candidates, 1))
    )


def parse_picks(answer: str, candidates: list[Chunk], limit: int) -> list[Chunk]:
    data = gate.parse(answer) or {"ids": []}
    ids = data.get("ids", [])
    if not isinstance(ids, list):
        return []
    picked = [
        candidates[i - 1] for i in ids if isinstance(i, int) and not isinstance(i, bool) and 1 <= i <= len(candidates)
    ]
    return picked[:limit]


async def expand_picks(picked: list[Chunk]) -> list[Chunk]:
    """고른 조각을 소항목 묶음으로 넓힌다. 같은 조각은 한 번만, 고른 순서대로"""
    groups = await store.groups_of(sorted({c.group_key for c in picked if c.kind == "drug"}))
    out: list[Chunk] = []
    seen: set[str] = set()
    for c in picked:
        for x in store.expand_group(c, groups.get(c.group_key, [c])):
            if x.chunk_id not in seen:
                seen.add(x.chunk_id)
                out.append(x)
    return out


async def judge(llm: LLM, question: str, info: str, evidence: list[Chunk]) -> gate.Verdicts:
    """A, B, C를 동시에 돌린다. 근거가 없으면 부르지 않고 모두 불충분"""
    if not evidence:
        return gate.EMPTY
    head = f"질문: {question}\n(질문자 정보: {info})\n근거 글:\n" + "\n".join(
        f"[c{i}] {store.show(c)}" for i, c in enumerate(evidence, 1)
    )
    a, b, c = await asyncio.gather(
        llm.complete(prompts.JUDGE_A_PROMPT + head),
        llm.complete(prompts.JUDGE_B_PROMPT + head),
        llm.complete(prompts.ANSWER_PROMPT + head),
    )
    da, db, dc = gate.parse(a) or {}, gate.parse(b) or {}, gate.parse(c) or {}
    return gate.Verdicts(
        a=str(da.get("verdict", "?")),
        b=str(db.get("verdict", "?")),
        b_direct=bool(db.get("direct", False)),
        c=str(dc.get("type", "?")),
    )


async def search(
    question: str,
    drug_codes: list[str],
    disease_codes: list[str],
    *,
    top_k: int = MAX_PICK,
    llm: LLM | None = None,
    timeout_sec: float | None = None,
    max_attempts: int | None = None,
    budget_sec: float | None = None,
) -> SearchResult:
    """근거 검색 + 판정. 통과하면 evidence, 아니면 빈 목록과 reason. 약도 질환도 없으면 OpenAI를 부르지 않는다"""
    llm = llm or OpenAIClient(timeout_sec, max_attempts)
    if budget_sec is None:
        return await _search(question, drug_codes, disease_codes, top_k=top_k, llm=llm)
    try:
        async with asyncio.timeout(budget_sec):
            return await _search(question, drug_codes, disease_codes, top_k=top_k, llm=llm)
    except TimeoutError:
        logger.warning("근거 검색이 제한 시간 %s초를 넘김", budget_sec)
        return SearchResult(reason="timeout")


async def _search(
    question: str, drug_codes: list[str], disease_codes: list[str], *, top_k: int, llm: LLM
) -> SearchResult:
    drugs = list(dict.fromkeys(drug_codes))
    diseases = list(dict.fromkeys(disease_codes))
    if not drugs and not diseases:
        return SearchResult(reason="no_code")
    result = SearchResult()
    clock = time.perf_counter()

    def lap(name: str) -> None:
        nonlocal clock
        now = time.perf_counter()
        result.seconds[name] = round(now - clock, 3)
        clock = now

    try:
        scope = await store.scope_chunks(drugs, diseases)
        if not scope:
            result.reason = "no_candidate"
            return result
        names: dict[str, str] = {c.drug_code: c.drug_name for c in scope if c.drug_code and c.drug_name}
        info = _asker_info(drugs, diseases, names)
        lap("scope")
        try:
            result.rewritten = await rewrite_question(llm, question, [names.get(d, d) for d in drugs], diseases)
        except LLMError:
            logger.warning("질문 재작성 실패, 원문으로 대신함")
            result.rewritten = (
                question  # 재작성이 틀려도 원문 순위가 같이 쓰여서(4장) 원문으로 대신해도 검색은 이어진다
            )
        lap("rewrite")
        vectors = await llm.embed([question, result.rewritten])
        lap("embed")
        candidates = await gather_candidates(scope, drugs, diseases, vectors[0], vectors[1], question, result.rewritten)
        lap("candidates")
        picked = parse_picks(
            await llm.complete(selection_prompt(question, result.rewritten, info, candidates)),
            candidates,
            min(top_k, MAX_PICK),
        )
        lap("select")
        if not picked:
            result.reason = "no_selection"
            return result
        expanded = await expand_picks(picked)
        result.verdicts = await judge(llm, question, info, expanded)
        lap("judge")
        blocked = gate.decide(question, result.verdicts)
        if blocked:
            result.reason = blocked
            return result
        result.evidence = [to_evidence(c) for c in expanded]
        return result
    except LLMError:
        logger.exception("근거 검색 중 OpenAI 호출 실패")
        result.evidence = []
        result.reason = "llm_error"
        return result
