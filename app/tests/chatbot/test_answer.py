"""질문부터 답까지 (#99 PR 2-1). 근거 검색과 OpenAI는 가짜로 바꿔 흐름만 확인 (CI에서 부르지 않음)."""

from typing import Any

from app.services.chatbot.answer import NO_EVIDENCE, REFER, clean_text
from app.services.chatbot.context import FixedInfo, UserDrug
from app.services.chatbot.llm import LLMError, Usage
from app.services.chatbot.pipeline import answer
from app.services.rag.gate import Verdicts
from app.services.rag.pipeline import Evidence, SearchResult
from app.tests.chatbot.test_route import classified, sync

S0 = FixedInfo(
    age=72,
    diseases=["고혈압", "제2형 당뇨병"],
    disease_ids=["HTN", "DM2"],
    drugs=[
        UserDrug("노바스크정5밀리그람", "암로디핀", "혈압", "1일 1회 아침", code="641900040"),
        UserDrug("다이아벡스정500밀리그램", "메트포르민", "당뇨", "1일 2회 식후", code="644300010"),
    ],
)
FULL = Verdicts(a="ENOUGH", b="ENOUGH", b_direct=True, c="FULL")
PARTIAL = Verdicts(a="PARTIAL", b="PARTIAL", b_direct=False, c="PARTIAL")
GRAPEFRUIT = Evidence(
    "D:641900040:S3", "drug_permit", "641900040", None, "S", "상호작용", "자몽주스와 함께 먹지 않는다"
)


def found(*evidence: Evidence, verdicts: Verdicts = FULL) -> SearchResult:
    return SearchResult(evidence=list(evidence), verdicts=verdicts)


class FakeSearch:
    """rag.search 자리. 받은 약 코드, 질환, 시간 예산을 남김"""

    def __init__(self, result: SearchResult | None = None) -> None:
        self.result = result or found(GRAPEFRUIT)
        self.calls: list[dict[str, Any]] = []

    async def __call__(
        self, question: str, drug_codes: list[str], disease_codes: list[str], *, budget_sec: float
    ) -> SearchResult:
        self.calls.append({"drugs": drug_codes, "diseases": disease_codes, "budget": budget_sec})
        return self.result


class FakeChat:
    """guard, classify, answer마다 정해 둔 답을 돌려주고 받은 글을 남김"""

    def __init__(self, classify: dict[str, Any] | None = None, reply: dict[str, Any] | Exception | None = None):
        self.answers: dict[str, Any] = {
            "guard": {"reason": "", "risk": "none"},
            "classify": classify or classified(),
            "answer": reply
            or {"answer_type": "normal", "content": "자몽주스와 함께 드시지 않는 게 좋아요.", "used_sources": []},
        }
        self.seen: dict[str, str] = {}
        self.calls: list[str] = []

    async def complete_json(
        self, system: str, messages: list[dict[str, str]], schema: dict[str, Any], name: str, usage: Usage
    ) -> dict[str, Any]:
        self.calls.append(name)
        self.seen[name] = messages[-1]["content"]
        a = self.answers[name]
        if isinstance(a, Exception):
            raise a
        return a


@sync
async def test_full_evidence_gives_normal_answer_with_sources():
    reply = {"answer_type": "normal", "content": "자몽주스는 피해 주세요.", "used_sources": ["D:641900040:S3", "X:1"]}
    chat, search = FakeChat(reply=reply), FakeSearch()
    r = await answer("자몽주스 마셔도 돼요?", S0, [], chat, search=search)
    assert (r.answer_type, r.content) == ("normal", "자몽주스는 피해 주세요.")
    assert r.sources == ["D:641900040:S3"]  # 근거에 없는 번호는 버림
    assert "자몽주스와 함께 먹지 않는다" in chat.seen["answer"]


@sync
async def test_partial_coverage_makes_partial_even_if_ai_says_normal():
    r = await answer(
        "자몽주스 마셔도 돼요?", S0, [], FakeChat(), search=FakeSearch(found(GRAPEFRUIT, verdicts=PARTIAL))
    )
    assert r.answer_type == "partial"


@sync
async def test_no_evidence_uses_fixed_copy_without_calling_answer():
    """근거가 없으면 AI를 부르지 않고 고정 문구 (설계 메모 6-1 문구표)"""
    chat = FakeChat()
    r = await answer("자몽주스 마셔도 돼요?", S0, [], chat, search=FakeSearch(SearchResult(reason="insufficient")))
    assert (r.answer_type, r.content, r.evidence_reason) == ("no_evidence", NO_EVIDENCE, "insufficient")
    assert "answer" not in chat.calls


@sync
async def test_ai_no_evidence_also_uses_fixed_copy():
    reply = {"answer_type": "no_evidence", "content": "아마 괜찮을 거예요", "used_sources": []}
    r = await answer("자몽주스 마셔도 돼요?", S0, [], FakeChat(reply=reply), search=FakeSearch())
    assert (r.answer_type, r.content) == ("no_evidence", NO_EVIDENCE)


@sync
async def test_target_drug_narrows_search_and_profile_diseases_are_passed():
    """대상 약이 있으면 그 약만, 질환은 처방전과 내 정보를 합친 id (#99 정할 것 4번, 10/20)"""
    search = FakeSearch()
    cls = classified(target_drug="노바스크정5밀리그람", target_source="question")
    await answer("노바스크는 언제 먹어요?", S0, [], FakeChat(classify=cls), search=search)
    assert search.calls[0]["drugs"] == ["641900040"] and search.calls[0]["diseases"] == ["HTN", "DM2"]


@sync
async def test_no_target_searches_all_user_drugs():
    search = FakeSearch()
    await answer("자몽주스 마셔도 돼요?", S0, [], FakeChat(), search=search)
    assert search.calls[0]["drugs"] == ["641900040", "644300010"]


@sync
async def test_search_budget_leaves_room_for_answer():
    """근거 검색 예산 = 25초 - 지금까지 걸린 시간 - 답 만들기 한 번(15초) (10/20 수인 결정)"""
    search = FakeSearch()
    await answer("자몽주스 마셔도 돼요?", S0, [], FakeChat(), search=search)
    assert 0 < search.calls[0]["budget"] <= 10


@sync
async def test_refer_appends_fixed_copy_once():
    cls = classified(category="refer", refer_kind="next_visit")
    reply = {"answer_type": "normal", "content": "신장에 부담이 될 수 있어요.", "used_sources": []}
    r = await answer("이 약 먹는데 신장이 걱정돼요", S0, [], FakeChat(classify=cls, reply=reply), search=FakeSearch())
    assert r.answer_type == "refer"
    assert r.content == f"신장에 부담이 될 수 있어요. {REFER['next_visit']}"


@sync
async def test_ai_refer_on_medication_keeps_refer_without_copy():
    """분류는 약인데 AI가 의료진 상담이 필요하다고 하면 refer로 두고 문구는 붙이지 않음 (로컬 실험과 같음)"""
    reply = {"answer_type": "refer", "content": "의료진과 상의해 주세요.", "used_sources": []}
    r = await answer("자몽주스 마셔도 돼요?", S0, [], FakeChat(reply=reply), search=FakeSearch())
    assert (r.answer_type, r.content) == ("refer", "의료진과 상의해 주세요.")


@sync
async def test_refer_without_evidence_sends_only_refer_copy():
    """의료진 상담인데 근거가 없으면 AI를 부르지 않고 상담 안내 문구만 (상담 대상이 약사로 바뀌지 않게, 10/20 수인 결정)"""
    chat = FakeChat(classify=classified(category="refer", refer_kind="soon"))
    r = await answer("요즘 자꾸 어지러워요", S0, [], chat, search=FakeSearch(SearchResult(reason="insufficient")))
    assert (r.answer_type, r.content) == ("refer", REFER["soon"])
    assert "answer" not in chat.calls
    reply = {"answer_type": "normal", "content": "다음 식사 후에 드세요.", "used_sources": []}
    cls = classified(category="refer", refer_kind="pharmacist")
    r = await answer("아침 약을 깜빡했어요", S0, [], FakeChat(classify=cls, reply=reply), search=FakeSearch())
    assert (r.answer_type, r.content) == ("refer", REFER["pharmacist"])


@sync
async def test_missed_dose_without_evidence_line_is_no_evidence():
    """약을 빠뜨린 질문은 근거에 그 안내가 없으면 AI가 무엇이라 하든 근거 없음 (로컬 실험 규칙)"""
    reply = {"answer_type": "normal", "content": "다음 식사 후에 드세요.", "used_sources": []}
    r = await answer("아침 약을 깜빡했어요", S0, [], FakeChat(reply=reply), search=FakeSearch())
    assert (r.answer_type, r.content) == ("no_evidence", NO_EVIDENCE)


@sync
async def test_out_of_scope_answers_briefly_without_search():
    search = FakeSearch()
    reply = {"answer_type": "normal", "content": "약이나 생활습관을 물어봐 주세요.", "used_sources": []}
    cls = classified(category="out_of_scope")
    r = await answer("오늘 날씨 어때요?", S0, [], FakeChat(classify=cls, reply=reply), search=search)
    assert (r.answer_type, search.calls) == ("normal", [])
    # 근거가 없어 AI가 no_evidence라고 해도 범위 밖은 짧은 응대를 그대로 (로컬 실험과 같음)
    reply = {"answer_type": "no_evidence", "content": "날씨는 알려 드리기 어려워요.", "used_sources": []}
    r = await answer("오늘 날씨 어때요?", S0, [], FakeChat(classify=cls, reply=reply), search=search)
    assert (r.answer_type, r.content) == ("normal", "날씨는 알려 드리기 어려워요.")


@sync
async def test_safety_and_clarify_stop_before_search():
    search = FakeSearch()
    r = await answer("약을 한꺼번에 많이 먹었어요", S0, [], FakeChat(), search=search)
    assert (r.answer_type, r.content, search.calls) == ("emergency", None, [])
    cls = classified(category="clarify", clarify_question="어떤 약을 말씀하시나요?")
    r = await answer("그거 먹어도 돼요?", S0, [], FakeChat(classify=cls), search=search)
    assert (r.answer_type, r.content, search.calls) == ("clarify", "어떤 약을 말씀하시나요?", [])


@sync
async def test_answer_failure_is_error():
    r = await answer("자몽주스 마셔도 돼요?", S0, [], FakeChat(reply=LLMError("timeout")), search=FakeSearch())
    assert (r.answer_type, r.content) == ("error", None)


@sync
async def test_reply_keeps_no_raw_question():
    question = "자몽주스 마셔도 돼요?"
    r = await answer(question, S0, [], FakeChat(), search=FakeSearch())
    assert question not in repr(r)


def test_clean_text_removes_marks():
    """글 규칙: 마크다운 기호, 이모지, 줄표, 가운뎃점을 지움 (설계 메모 7-12)"""
    assert clean_text("**자몽**은 피해요 — 약사 · 의사에게 😀") == "자몽은 피해요, 약사, 의사에게"
    assert clean_text("- 첫째\n# 제목") == "첫째\n제목"
