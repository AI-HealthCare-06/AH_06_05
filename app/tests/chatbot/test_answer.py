"""질문부터 답까지 (#99 PR 2-1). 근거 검색과 OpenAI는 가짜로 바꿔 흐름만 확인 (CI에서 부르지 않음)."""

from dataclasses import replace
from typing import Any

from app.services.chatbot.answer import NO_EVIDENCE, REFER, clean_text, output_guard
from app.services.chatbot.context import FixedInfo, PairWarning, UserDrug
from app.services.chatbot.llm import LLMError, Usage
from app.services.chatbot.pipeline import ANALYSIS_GUIDE, answer
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


# ── 출력 가드레일: 근거에 없는 숫자나 복용 지시 (10/20 멘토링 수인 안, 10/25 정리 뒤에 두고 걸리면 근거 없음 고정 문구) ──
async def _guarded(content: str, cls: dict[str, Any] | None = None):
    reply = {"answer_type": "normal", "content": content, "used_sources": ["D:641900040:S3"]}
    return await answer("자몽주스 마셔도 돼요?", S0, [], FakeChat(classify=cls, reply=reply), search=FakeSearch())


@sync
async def test_output_guard_blocks_number_not_in_evidence(caplog):
    r = await _guarded("자몽주스는 하루 3잔까지는 괜찮아요.")
    assert (r.answer_type, r.content, r.sources) == ("no_evidence", NO_EVIDENCE, [])
    assert r.evidence_reason == "output_guard:number"  # 대화 API 로그(메시지 번호와 같이)에 이유가 남게
    assert "출력 가드레일" in caplog.text and "자몽" not in caplog.text  # 답 글은 로그에 남기지 않음


@sync
async def test_output_guard_allows_numbers_from_prescription():
    """고정 정보(처방대로 먹는 법, 약 이름)에 있는 숫자와 때는 근거로 봄"""
    r = await _guarded("노바스크정5밀리그람은 1일 1회 아침에 드세요. 자몽주스는 피해 주세요.")
    assert r.answer_type == "normal"


@sync
async def test_output_guard_allows_safety_numbers():
    assert (await _guarded("숨이 차면 바로 119에 전화해 주세요.")).answer_type == "normal"


@sync
async def test_output_guard_reads_korean_count_words():
    assert (await _guarded("다이아벡스는 하루 두 번 드세요.")).answer_type == "normal"  # 처방 1일 2회
    assert (await _guarded("한 번에 세 알 드셔도 괜찮아요.")).answer_type == "no_evidence"


@sync
async def test_output_guard_blocks_dose_change_not_in_evidence():
    assert (await _guarded("어지러우면 노바스크를 끊으세요.")).answer_type == "no_evidence"
    assert (await _guarded("혈압이 높으면 약을 늘려도 돼요.")).answer_type == "no_evidence"
    assert (await _guarded("노바스크를 임의로 끊지 마세요.")).answer_type == "normal"  # 하지 말라는 말은 지시가 아님


@sync
async def test_output_guard_blocks_timing_not_in_prescription_or_evidence():
    assert (await _guarded("다이아벡스는 자기 전에 드세요.")).answer_type == "no_evidence"  # 처방은 식후


@sync
async def test_output_guard_on_refer_keeps_refer_copy_only():
    cls = classified(category="refer", refer_kind="next_visit")
    r = await _guarded("신장이 걱정되면 하루 4번으로 나눠 드세요.", cls)
    assert (r.answer_type, r.content) == ("refer", REFER["next_visit"])


@sync
async def test_output_guard_ignores_lifestyle_change_next_to_drug():
    """바꾸라는 말은 대상이 약일 때만 (10/25 점검: 약 이름과 같은 문장의 "술을 줄이세요"를 거르던 것)"""
    assert (await _guarded("다이아벡스를 드시는 동안 술을 줄이세요.")).answer_type == "normal"
    assert (await _guarded("약 드시는 동안 담배를 끊으세요.")).answer_type == "normal"
    assert (await _guarded("노바스크는 다른 약으로 바꾸세요.")).answer_type == "no_evidence"


@sync
async def test_output_guard_ignores_list_numbers():
    r = await _guarded("1. 자몽주스는 피해 주세요.\n2. 노바스크는 아침에 드세요.\n3. 물을 충분히 마셔요.")
    assert r.answer_type == "normal"


@sync
async def test_output_guard_counts_only_dose_words():
    """세는 말은 먹는 양과 "하루 ○ 번"만 숫자로 봄 (근거도 고정 정보도 없는 범위 밖 응대에서 "한 번 더"를 거르던 것)"""
    info = FixedInfo(age=None)
    assert output_guard("궁금한 점이 있으면 한 번 더 물어봐 주세요.", [], info) is None
    assert output_guard("하루 세 번 드세요.", [], info) == "number"
    assert output_guard("한 번에 두 알 드세요.", [], info) == "number"


@sync
async def test_missed_dose_rule_reads_only_drug_permit():
    """약을 빠뜨린 질문은 허가정보 문장에 그 안내가 있을 때만 답함. 팩트표 "끼니 거르지 않기"를 그 안내로 보던 것 (10/25 실제 답 확인)"""
    meal = Evidence(
        "F:DM2:life:규칙적인 식사", "lifestyle_fact", None, "DM2", None, "규칙적인 식사", "끼니 거르지 않기"
    )
    reply = {"answer_type": "normal", "content": "생각났을 때 바로 드세요.", "used_sources": []}
    r = await answer("다이아벡스를 한 번 깜빡했어요", S0, [], FakeChat(reply=reply), search=FakeSearch(found(meal)))
    assert (r.answer_type, r.content) == ("no_evidence", NO_EVIDENCE)


@sync
async def test_missed_dose_rule_reads_forgot_words():
    """ "잊었어요"도 빠뜨린 질문이고, 허가정보의 "잊은 경우"도 그 안내로 봄 (10/25 점검)"""
    reply = {"answer_type": "normal", "content": "생각났을 때 바로 드세요.", "used_sources": []}
    r = await answer("약 먹는 걸 잊었어요", S0, [], FakeChat(reply=reply), search=FakeSearch())
    assert r.answer_type == "no_evidence"
    forgot = Evidence(
        "D:644300010:P2", "drug_permit", "644300010", None, "P", "용법용량", "복용을 잊은 경우 생각난 즉시 복용한다"
    )
    r = await answer("약 먹는 걸 잊었어요", S0, [], FakeChat(reply=reply), search=FakeSearch(found(forgot)))
    assert r.answer_type == "normal"


def test_output_guard_timing_only_on_instructions():
    """먹는 때는 시키는 말에만 ("먹으면 졸릴 수 있어요" 같은 설명은 거르지 않음, 10/25 점검)"""
    assert output_guard("저녁에 약을 먹으면 졸릴 수 있어요.", [GRAPEFRUIT], S0) is None
    assert output_guard("다이아벡스는 자기 전에 드시면 돼요.", [GRAPEFRUIT], S0) == "timing"
    assert output_guard("노바스크는 공복에 먹으세요.", [GRAPEFRUIT], S0) == "timing"


def test_output_guard_timing_reads_previous_drug_sentence():
    """약 이름을 앞 문장에 쓰고 다음 문장에서 먹는 때를 말해도 봄 (10/25 점검)"""
    assert output_guard("노바스크는 혈압약이에요. 자기 전에 드셔도 괜찮아요.", [GRAPEFRUIT], S0) == "timing"
    assert output_guard("자몽주스는 피해 주세요. 물은 아침에 드셔도 돼요.", [GRAPEFRUIT], S0) is None


@sync
async def test_forgetting_drug_name_is_not_missed_dose():
    """ "잊"은 약을 먹는 것을 잊은 말일 때만 빠뜨린 질문으로 봄 ("약 이름을 잊었어요"는 아님, 10/25 점검)"""
    reply = {
        "answer_type": "normal",
        "content": "노바스크정5밀리그람과 다이아벡스정500밀리그램을 드시고 있어요.",
        "used_sources": [],
    }
    r = await answer("약 이름을 잊었어요", S0, [], FakeChat(reply=reply), search=FakeSearch())
    assert r.answer_type == "normal"
    r = await answer("아침 약을 잊었어요", S0, [], FakeChat(reply=reply), search=FakeSearch())
    assert r.answer_type == "no_evidence"


@sync
async def test_skipping_meal_is_not_missed_dose():
    """빠뜨린 약 규칙은 약 이야기일 때만 (질문에 약이나 약 이름, 또는 분류가 약, 상담). 끼니를 거르는 질문은 팩트표로 답함 (10/25 점검)"""
    meal = Evidence(
        "F:DM2:life:규칙적인 식사",
        "lifestyle_fact",
        None,
        "DM2",
        None,
        "규칙적인 식사",
        "끼니 거르지 않기(저혈당 위험)",
    )
    reply = {"answer_type": "normal", "content": "끼니를 거르면 저혈당 위험이 있어요.", "used_sources": []}
    cls = classified(category="lifestyle")
    for q in ("끼니를 거르면 안 되나요?", "끼니를 거르면 어떻게 되는지 알려 주세요"):
        r = await answer(q, S0, [], FakeChat(classify=cls, reply=reply), search=FakeSearch(found(meal)))
        assert r.answer_type == "normal", q
    # 약 이름이 없어도 분류가 약이면 빠뜨린 질문 ("깜빡했어요"만 보낸 경우)
    r = await answer("어제 깜빡했어요", S0, [], FakeChat(reply=reply), search=FakeSearch(found(meal)))
    assert r.answer_type == "no_evidence"


MISSED_QUESTIONS = (
    "복용하는 걸 잊었어요",
    "오늘 약 먹는 걸 까먹었어요",
    "약 먹는 거 잊었어요",
    "어제 약을 못 챙겼어요",
    "약을 잊으면 어떻게 해요?",  # 빠뜨렸을 때를 묻는 말은 잡음 ("잊을까 봐"는 아님)
    "어제 약을 안 챙겨 먹었어요",
    "어제 약을 못 챙겨 먹었어요",
    "약 먹는 시간을 놓쳤어요",
    "약을 하루 걸렀어요",
    "당뇨약을 거른 것 같아요",  # "거른" (10/26 수인 결정)
    "약 먹었는지 기억이 안 나요",  # 두 번 먹을 수 있어 빠뜨린 질문처럼 다룸 (10/25 수인 결정)
    "약 먹었는지 모르겠어요",
    # 약이 없어도 "잊어버렸", "잊고", "잊었"만으로 봄 (main 규칙이 잡던 것, 10/26 수인 결정)
    "아침 거 잊어버렸어요",
    "어제 잊고 그냥 잤어요",
    "저녁 걸 잊었어요",
    "약을 잊어먹었어요",
)
NOT_MISSED_QUESTIONS = (
    "약 이름을 까먹었어요",
    "약 먹는 법을 잊었어요",
    "약 이름을 잊어버렸어요",
    "약을 잊어버릴까 봐 걱정이에요",
    "약을 잊지 않으려면 어떻게 해요?",
    "약을 잊지 말라고 알려 주세요",
    "약국 가는 시간을 놓쳤어요",
    "약 먹고 버스를 놓쳤어요",
)


def _typo_variants(q: str) -> list[str]:
    """고령 사용자 입력처럼 바꾼 글: 붙여 씀, 글자마다 띄움, 받침 ㅆ을 ㅅ으로, 끝말 "요"를 "여"로 (10/25 점검)"""

    def no_ss(s: str) -> str:
        return "".join(
            chr(ord(c) - 1) if 0 <= ord(c) - 0xAC00 < 11172 and (ord(c) - 0xAC00) % 28 == 20 else c for c in s
        )

    joined = q.replace(" ", "")
    return [q, joined, " ".join(joined), no_ss(q), q.replace("요", "여"), no_ss(joined)]


@sync
async def test_missed_dose_question_words():
    """빠뜨린 질문 낱말 (10/25 다시 의심, 점검: 놓치던 말과 잘못 잡던 말). 띄어쓰기와 흔한 오타가 있어도 같게"""
    reply = {"answer_type": "normal", "content": "걱정하지 않으셔도 돼요.", "used_sources": []}
    for q in MISSED_QUESTIONS:
        for v in _typo_variants(q):
            r = await answer(v, S0, [], FakeChat(reply=reply), search=FakeSearch())
            assert r.answer_type == "no_evidence", v
    for q in NOT_MISSED_QUESTIONS:
        for v in _typo_variants(q):
            r = await answer(v, S0, [], FakeChat(reply=reply), search=FakeSearch())
            assert r.answer_type == "normal", v


# 10/25 실제 답: 되물음 다음 차례("노바스크요")에 허가정보에 없는 빠뜨린 약 지시가 나감
MISSED_ADVICE = (
    "노바스크정은 고혈압에 쓰는 약이에요. 약을 안 챙겨 먹었다면, 다음 복용 시간에 바로 복용하세요. "
    "하지만, 복용을 잊은 경우에는 두 배로 먹지 말고, 정해진 시간에 맞춰 복용하세요."
)


def test_output_guard_blocks_missed_dose_advice_not_in_permit():
    """답이 빠뜨린 상황을 말하면서 먹으라고 하는데 허가정보에 그 안내가 없으면 거름 (10/25 점검)"""
    assert output_guard(MISSED_ADVICE, [GRAPEFRUIT], S0) == "missed"
    assert output_guard("생각났을 때 바로 드세요.", [GRAPEFRUIT], S0) == "missed"
    assert output_guard("약을 안 챙겨 먹었다면, 다음 복용 시간에 바로 복용하세요.", [GRAPEFRUIT], S0) == "missed"
    assert output_guard("복용 시간을 놓치셨다면 바로 드세요.", [GRAPEFRUIT], S0) == "missed"
    # 10/25 실제 답 ("다이아벡스요" 차례): "먹은", "드신" 꼴
    assert (
        output_guard("약을 안 챙겨 먹은 경우, 다음 복용 시간에 정상적으로 복용하시면 돼요.", [GRAPEFRUIT], S0)
        == "missed"
    )
    assert output_guard("약을 못 챙겨 드신 경우에는 다음 복용 시간에 드세요.", [GRAPEFRUIT], S0) == "missed"
    assert output_guard("약을 빠뜨리지 않도록 약통을 쓰세요.", [GRAPEFRUIT], S0) is None  # 먹으라는 말이 없음
    # 하지 않도록 하는 조언이나 주의는 거르지 않음 (10/25 점검: 줄기만 넣어 잘못 잡던 것)
    for s in (
        "깜빡하지 않도록 알람을 맞추고 식후에 드세요.",
        "빼먹지 않게 약통에 넣고 식후에 드세요.",
        "잊어버리지 않도록 식후에 드세요.",
        "약을 빠뜨리지 않도록 약통에 넣고 식후에 드세요.",
        "약을 안 챙겨 드시면 혈압이 오를 수 있으니 매일 식후에 드세요.",
        "약을 안 챙겨 드신다면 혈압이 오를 수 있으니 매일 식후에 드세요.",  # "드신"을 더한 뒤 점검
        "식사를 놓친 경우에는 약을 드시기 전에 간단히 드세요.",  # 끼니 이야기
    ):
        assert output_guard(s, [GRAPEFRUIT], S0) is None, s
    forgot = Evidence(
        "D:644300010:P2", "drug_permit", "644300010", None, "P", "용법용량", "복용을 잊은 경우 생각난 즉시 복용한다"
    )
    assert output_guard("복용을 잊은 경우 생각났을 때 바로 드세요.", [forgot], S0) is None


@sync
async def test_missed_dose_advice_after_clarify_turn():
    """되물음 다음 차례는 질문에 빠뜨린 말이 없어도 답에서 거름 (10/25 실제 답)"""
    past = [
        {"role": "user", "content": "어제 약을 안 챙겨 먹었는데 어떡해요?"},
        {"role": "assistant", "content": "어떤 약을 말씀하시는 건가요?"},
    ]
    reply = {"answer_type": "normal", "content": MISSED_ADVICE, "used_sources": []}
    r = await answer("노바스크요", S0, past, FakeChat(reply=reply), search=FakeSearch())
    assert (r.answer_type, r.evidence_reason) == ("no_evidence", "output_guard:missed")


def test_output_guard_blocks_stop_taking():
    """약을 먹지 말라는 말은 근거에 없으면 거름 (10/26 수인 결정, 함께 먹지 말라는 경고도 AI가 만들지 않음 NFR-032)"""
    for s in (
        "노바스크는 복용하지 마세요.",
        "노바스크는 드시지 마세요.",
        "약을 먹지 마세요.",
        "오늘은 약을 드시지 말고 병원에 가세요.",
        "술과 함께 약을 드시지 마세요.",  # 받아들인 대가 (10/26 수인 결정)
    ):
        assert output_guard(s, [GRAPEFRUIT], S0) == "change", s
    for s in (
        "약을 임의로 중단하지 마세요.",
        "자몽주스와 함께 드시지 마세요.",
        "공복에 드시지 마세요.",
    ):
        assert output_guard(s, [GRAPEFRUIT], S0) is None, s
    stop = Evidence("D:641900040:P9", "drug_permit", "641900040", None, "P", "주의", "임부는 복용하지 마십시오")
    assert output_guard("임부는 노바스크를 복용하지 마세요.", [stop], S0) is None  # 근거에 있는 말


def test_output_guard_blocks_ok_to_stop():
    """약을 멈춰도 된다는 말도 근거에 없으면 거름 (#126 채연 리뷰, 10/26 수인 결정: 미루지 않고 고침)"""
    for s in (
        "혈압이 정상이면 노바스크는 안 드셔도 돼요.",
        "오늘 하루는 약을 안 드셔도 괜찮아요.",
        "며칠 약을 쉬어도 돼요.",
        "노바스크는 드시지 않아도 돼요.",
        "노바스크는 먹지 않아도 괜찮아요.",
        "노바스크는 드시지 않는 게 좋아요.",  # 10/26 점검에서 찾은 같은 종류
        "노바스크는 그만 드셔야 해요.",
        "노바스크는 이제 안 먹어도 돼요.",  # 약 이름이 8글자보다 앞 (점검)
        "노바스크를 하루 쉬셔도 돼요.",
    ):
        assert output_guard(s, [GRAPEFRUIT], S0) == "change", s
    for s in (
        "자몽주스는 드시지 않는 게 좋아요.",  # 약이 아닌 것
        "커피는 안 드셔도 돼요.",
        "약을 드시고 푹 쉬어도 돼요.",  # 약을 먹고 쉬라는 말
        "약을 임의로 쉬지 마세요.",
        "약 드시고 쉬세요.",
    ):
        assert output_guard(s, [GRAPEFRUIT], S0) is None, s


@sync
async def test_missed_dose_question_classified_out_of_scope():
    """분류가 범위 밖으로 나와도 약을 빠뜨린 질문이면 근거 없음 (10/25 실제 답이 normal로 나간 길, 가짜 AI로 확인)"""
    cls = classified(category="out_of_scope")
    reply = {"answer_type": "normal", "content": "다음부터 잘 챙겨 드시면 돼요.", "used_sources": []}
    r = await answer("어제약을못챙겨먹엇어여", S0, [], FakeChat(classify=cls, reply=reply), search=FakeSearch())
    assert (r.answer_type, r.content) == ("no_evidence", NO_EVIDENCE)
    # 약 이야기가 아니면 범위 밖 응대 그대로. "약속", "약국"의 "약"은 약으로 보지 않음 (10/26 수인 결정)
    reply = {"answer_type": "normal", "content": "약이나 생활습관을 물어봐 주세요.", "used_sources": []}
    for q in (
        "어제 친구 생일을 깜빡했어요",
        "친구랑 약속을 깜빡했어요",
        "약국 가는 걸 깜빡했어요",
    ):
        r = await answer(q, S0, [], FakeChat(classify=cls, reply=reply), search=FakeSearch())
        assert r.answer_type == "normal", q
    # 붙여 쓴 "약 하나", "아예 약을"은 약으로 봄. 그래서 "예약"도 약으로 봄 (안전한 쪽, 10/26 수인 결정)
    for q in ("약하나 빼먹었어요", "아예약을 안먹었어요", "병원 예약을 깜빡했어요"):
        r = await answer(q, S0, [], FakeChat(classify=cls, reply=reply), search=FakeSearch())
        assert r.answer_type == "no_evidence", q


@sync
async def test_meal_skip_in_permit_is_not_missed_dose_guide():
    """허가정보의 끼니 문장은 빠뜨린 약 안내로 보지 않음. "거르", "걸렀", "거른"은 질문에만 씀 (10/26 수인 결정)"""
    reply = {"answer_type": "normal", "content": "다음 식사 때 꼭 챙기세요.", "used_sources": []}
    for text in (
        "식사를 거른 경우 저혈당이 나타날 수 있다",
        "식사를 거르면 저혈당이 나타날 수 있다",
        "식사를 걸렀을 때는 저혈당에 주의한다",
    ):
        meal = Evidence("D:644300010:P5", "drug_permit", "644300010", None, "P", "주의", text)
        r = await answer("다이아벡스를 깜빡했어요", S0, [], FakeChat(reply=reply), search=FakeSearch(found(meal)))
        assert r.answer_type == "no_evidence", text


@sync
async def test_this_drug_name_is_used_as_plain_text():
    """약 이름은 바꿀 글자 그대로 넣음. 이름에 역슬래시가 있어도 정규식 치환 문법으로 읽지 않음 (#135 채연 리뷰)"""
    odd = replace(S0, drugs=[UserDrug("가짜\\1정\\g<0>", "성분", "", "", code="641900040")])
    row = Evidence("D:641900040:S1", "drug_permit", "641900040", None, "S", "주의", "이 약의 혈중 농도가 증가")
    chat = FakeChat()
    await answer("가짜 약 주의할 점 있어요?", odd, [], chat, search=FakeSearch(found(row)))
    assert "가짜\\\\1정\\\\g<0>의 혈중 농도" in chat.seen["answer"]


@sync
async def test_this_drug_in_permit_becomes_drug_name():
    """허가 원문의 "이 약"은 AI에게 넘길 때 그 약 이름으로 (다른 약 근거의 "이 약"을 엉뚱한 약으로 옮긴 문제, 10/26 채연 Q1)"""
    texts = ("로바가정과 병용하는 경우, 이 약의 혈중 농도가 증가", "이약을 투여 받는 동안", "이 약물을 투여받는 동안")
    rows = [
        Evidence(f"D:641900040:S{i}", "drug_permit", "641900040", None, "S", "주의", t) for i, t in enumerate(texts)
    ]
    rows.append(
        Evidence("D:641900040:S9", "drug_permit", "641900040", None, "S", "주의", "효과가 있는 것이 약효를 높임")
    )
    other_words, comma_end = (
        "이 약국, 이 약사, 이 약제, 이 약효, 이 약품, 이 약리작용, 이 약가 인하",
        "다른 약과 이 약, 함께 두지 말 것: 이 약",
    )
    rows.append(Evidence("D:641900040:S8", "drug_permit", "641900040", None, "S", "주의", other_words))
    rows.append(Evidence("D:641900040:S7", "drug_permit", "641900040", None, "S", "주의", comma_end))
    chat = FakeChat()
    await answer("노바스크 주의할 점 있어요?", S0, [], chat, search=FakeSearch(found(*rows)))
    sent = chat.seen["answer"]
    assert "노바스크정5밀리그람의 혈중 농도" in sent and "노바스크정5밀리그람을 투여" in sent
    assert sent.count("노바스크정5밀리그람을 투여받는") == 1 and "것이 약효" in sent
    assert not any(w in sent for w in ("이 약의", "이약을", "이 약물"))
    # 뒤가 조사나 한글이 아닌 글자일 때만 바꿈. 다른 낱말("이 약효", "이 약리작용")은 그대로 (#135 채연 리뷰 참고)
    assert other_words in sent
    assert "다른 약과 노바스크정5밀리그람, 함께 두지 말 것: 노바스크정5밀리그람" in sent


@sync
async def test_analysis_chip_answers_with_guide_without_ai():
    """분석 칩은 근거 검색과 답 AI 없이 분석 결과 화면 안내로. AI가 허가정보를 분석 결론처럼 말함 (10/27 측정 3번 중 3번)"""
    chat, search = FakeChat(classify=classified(category="out_of_scope")), FakeSearch()
    r = await answer("이번 분석에서 가장 조심할 건 뭔가요?", S0, [], chat, search=search)
    assert (r.answer_type, r.content) == ("normal", ANALYSIS_GUIDE)
    assert "answer" not in chat.calls and search.calls == [] and r.sources == []


@sync
async def test_analysis_guide_takes_reworded_chip():
    chat = FakeChat(classify=classified(category="out_of_scope"))
    r = await answer("이번 분석에서 제일 주의할 약이 뭐예요?", S0, [], chat, search=FakeSearch())
    assert r.content == ANALYSIS_GUIDE


# ⑤ 이미 계산된 점검 결과로 답하기 (설계 메모 7-12, #116 safetyCard, 10/26 수인 결정)
NSAID = PairWarning(
    31, ("낙센에프서방정1000밀리그램(나프록센)", "스로펜정(이부프로펜)"), "효과가 비슷한 약을 함께 드시고 있어요"
)
STATIN = PairWarning(
    32,
    ("아토르스타정10밀리그램(아토르바스타틴칼슘삼수화물)", "로바가정10밀리그램(로수바스타틴칼슘)"),
    "효과가 비슷한 약을 함께 드시고 있어요",
)
S_WARN = replace(S0, analysis_id=7, pair_warnings=[NSAID, STATIN])


@sync
async def test_own_drugs_question_answers_with_check_result_without_ai():
    """먹는 약끼리 묻는 질문은 분석의 경고를 템플릿으로 답하고 근거 검색과 답 AI를 부르지 않음 (NFR-032).
    경고 사이와 끝 문장 앞은 빈 줄 (좁은 화면에서 접힌 줄과 다음 덩어리가 구분되지 않아서)"""
    chat, search = FakeChat(classify=classified(about_user_drugs=True)), FakeSearch()
    r = await answer("같이 먹으면 안 되는 약 있어?", S_WARN, [], chat, search=search)
    assert r.answer_type == "normal" and r.safety_card == {"analysisId": 7, "warningIds": [31, 32]}
    assert r.content == (
        "분석에서 확인된, 같이 먹을 때 주의할 점이에요.\n"
        "낙센에프서방정1000밀리그램(나프록센), 스로펜정(이부프로펜): 효과가 비슷한 약을 함께 드시고 있어요\n\n"
        "아토르스타정10밀리그램(아토르바스타틴칼슘삼수화물), 로바가정10밀리그램(로수바스타틴칼슘): "
        "효과가 비슷한 약을 함께 드시고 있어요\n\n"
        "위 내용은 분석 결과에서 자세히 볼 수 있어요. 약사에게 확인해 주세요."
    )
    assert "answer" not in chat.calls and search.calls == [] and r.sources == []


@sync
async def test_analysis_question_for_doctor_stays_refer():
    chat = FakeChat(classify=classified(category="refer", refer_kind="next_visit"))
    r = await answer("이번 분석 보고 약을 끊어도 되나요?", S0, [], chat, search=FakeSearch())
    assert r.answer_type == "refer"


@sync
async def test_own_drugs_question_without_warning_goes_to_search():
    """경고가 없으면 "걸린 항목이 없어요"로 답하지 않고 지금처럼 근거 검색 (안전하다고 읽힐 수 있어서)"""
    chat, search = FakeChat(classify=classified(about_user_drugs=True)), FakeSearch()
    r = await answer("같이 먹으면 안 되는 약 있어?", replace(S0, analysis_id=7), [], chat, search=search)
    assert r.safety_card is None and "answer" in chat.calls and search.calls


@sync
async def test_other_questions_do_not_use_check_result():
    """먹는 약끼리 묻지 않으면 경고가 있어도 지금처럼 근거로 답함"""
    chat = FakeChat(classify=classified(about_user_drugs=False))
    r = await answer("자몽주스 마셔도 돼요?", S_WARN, [], chat, search=FakeSearch())
    assert r.safety_card is None and "answer" in chat.calls


@sync
async def test_check_result_for_doctor_question_ends_with_refer_guide():
    """끊거나 바꾸려는 질문(next_visit)과 증상(soon)은 경고를 보여 주고 끝 문장을 그 상담 문구로 (#134 리뷰 1번, 10/27 수인 결정).
    약을 끊는 건 의사 판단이라 약사 안내로 끝나면 상담 대상이 바뀜"""
    for kind in ("next_visit", "soon"):
        chat = FakeChat(classify=classified(category="refer", refer_kind=kind, about_user_drugs=True))
        r = await answer("이 약들 끊어도 되는지, 같이 먹어도 되는지 궁금해요", S_WARN, [], chat, search=FakeSearch())
        assert r.answer_type == "refer" and r.safety_card == {"analysisId": 7, "warningIds": [31, 32]}, kind
        assert r.content.startswith("분석에서 확인된, 같이 먹을 때 주의할 점이에요.\n낙센에프"), kind
        assert r.content.endswith("드시고 있어요\n\n" + REFER[kind]) and "약사에게" not in r.content, kind
        assert "answer" not in chat.calls, kind


@sync
async def test_check_result_for_pharmacist_question_keeps_tail():
    chat = FakeChat(classify=classified(category="refer", refer_kind="pharmacist", about_user_drugs=True))
    r = await answer("낙센에프랑 스로펜 같이 먹어도 돼요?", S_WARN, [], chat, search=FakeSearch())
    assert r.answer_type == "normal" and r.content.endswith(
        "위 내용은 분석 결과에서 자세히 볼 수 있어요. 약사에게 확인해 주세요."
    )


@sync
async def test_non_drug_intake_question_skips_check_result():
    """술, 음식, 영양제처럼 점검에 없는 것을 같이 물으면 분류가 먹는 약끼리로 흔들려도 템플릿을 쓰지 않음.
    약끼리 경고만 나가면 술은 괜찮다고 읽힐 수 있음 (#134 리뷰 2번, 실제 분류 10번 중 3번, 10/27 수인 결정)"""
    for q in (
        "다이아벡스랑 술 같이 마셔도 돼요?",
        "이 약들 먹으면서 자몽주스 마셔도 돼요?",
        "영양제랑 같이 먹어도 돼요?",
    ):
        chat, search = FakeChat(classify=classified(about_user_drugs=True)), FakeSearch()
        r = await answer(q, S_WARN, [], chat, search=search)
        assert r.safety_card is None and "answer" in chat.calls and search.calls, q
    chat = FakeChat(classify=classified(about_user_drugs=True))
    r = await answer("수술 전에 이 약들 같이 먹어도 돼요?", S_WARN, [], chat, search=FakeSearch())
    assert r.safety_card is not None  # "수술"의 "술"은 술이 아님


@sync
async def test_analysis_chip_with_warnings_answers_with_check_result():
    """경고가 있는 분석의 분석 칩은 분석 안내보다 ⑤ 점검 결과가 먼저 (#134와 합칠 때 채연 리뷰)"""
    chat = FakeChat(classify=classified(category="out_of_scope"))
    r = await answer("이번 분석에서 가장 조심할 건 뭔가요?", S_WARN, [], chat, search=FakeSearch())
    assert r.safety_card == {"analysisId": 7, "warningIds": [31, 32]} and "answer" not in chat.calls


@sync
async def test_this_analysis_drug_question_answers_from_evidence():
    """질문에 "이번 분석"이 들어가도 약 하나의 복용법이나 부작용을 물으면 분석 안내나 점검 결과가 아니라 근거로 답함
    (#135 채연 리뷰: 실제 분류 10번 중 10번 분석 안내만 나옴)"""
    for q in ("이번 분석에 나온 노바스크는 어떻게 먹어야 하나요?", "이번 분석 결과에 나온 다이아벡스 부작용이 뭐예요?"):
        for info in (S0, S_WARN):
            chat = FakeChat(classify=classified(category="medication"))
            r = await answer(q, info, [], chat, search=FakeSearch())
            assert r.content != ANALYSIS_GUIDE and r.safety_card is None and "answer" in chat.calls, q
