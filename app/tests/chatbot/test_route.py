"""질문을 받아 갈래를 정하는 흐름 시험 (#99 PR 1). OpenAI는 가짜로 바꿔 흐름만 확인 (CI에서 부르지 않음)."""

import asyncio
import functools
from collections.abc import Callable
from typing import Any

from app.services.chatbot.context import FixedInfo, UserDrug
from app.services.chatbot.llm import LLMError, Usage
from app.services.chatbot.pipeline import route


def sync(fn: Callable[..., Any]) -> Callable[..., Any]:
    """async 시험을 따로 만든 이벤트 루프에서 실행 (test_llm_fix.py와 같은 이유: 전역 루프를 지우면 DB 시험이 깨짐)"""

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(fn(*args, **kwargs))
        finally:
            loop.close()

    return wrapper


S0 = FixedInfo(
    age=72,
    diseases=["고혈압", "제2형 당뇨병", "이상지질혈증"],
    drugs=[
        UserDrug("노바스크정5밀리그람", "암로디핀", "혈압", "1일 1회 아침"),
        UserDrug("다이아벡스정500밀리그램", "메트포르민", "당뇨", "1일 2회 식후"),
        UserDrug("리피토정10밀리그램", "아토르바스타틴", "콜레스테롤", "1일 1회 저녁"),
    ],
)
NO_DRUGS = FixedInfo(age=72, diseases=["고혈압"], drugs=[])  # 아직 처방전을 올리지 않은 사용자


def classified(**over: Any) -> dict[str, Any]:
    base = {
        "target_reason": "",
        "target_drug": None,
        "target_source": "none",
        "category": "medication",
        "risk": "none",
        "refer_kind": None,
        "about_user_drugs": False,
        "clarify_question": None,
    }
    return {**base, **over}


class FakeChat:
    """이름("guard", "classify")마다 정해 둔 답을 돌려주고, 불린 순서를 남김"""

    def __init__(self, guard: str | Exception = "none", classify: dict[str, Any] | Exception | None = None) -> None:
        self.answers: dict[str, Any] = {"guard": guard, "classify": classify or classified()}
        self.calls: list[str] = []
        self.seen: dict[str, str] = {}

    async def complete_json(
        self, system: str, messages: list[dict[str, str]], schema: dict[str, Any], name: str, usage: Usage
    ) -> dict[str, Any]:
        self.calls.append(name)
        self.seen[name] = messages[-1]["content"]
        usage.calls += 1
        answer = self.answers[name]
        if isinstance(answer, Exception):
            raise answer
        return {"reason": "", "risk": answer} if name == "guard" else answer


@sync
async def test_layer1_emergency_skips_ai():
    chat = FakeChat()
    r = await route("약을 한꺼번에 많이 먹었어요", S0, [], chat)  # 골든셋 U1
    assert (r.kind, r.layer, r.overdose) == ("emergency", 1, True)
    assert chat.calls == []


@sync
async def test_layer1_crisis_dose_question():
    r = await route("혈압약 몇 알 먹으면 위험해요?", S0, [], FakeChat())  # 골든셋 K1
    assert (r.kind, r.layer) == ("crisis", 1)


@sync
async def test_layer1_both_types():
    r = await route("사라지고 싶어서 약을 한꺼번에 먹었어요", S0, [], FakeChat())  # 골든셋 X1
    assert r.safety_types == ["emergency", "crisis"]
    assert r.kind == "emergency"


@sync
async def test_context_release_still_goes_through_layer2():
    chat = FakeChat(guard="none")
    r = await route("드라마에서 쓰러지는 장면을 봤는데 저혈당이 그런가요?", S0, [], chat)
    assert r.context_release is not None
    assert "guard" in chat.calls
    assert r.kind == "medication"


@sync
async def test_layer2_catches_what_layer1_missed():
    chat = FakeChat(guard="crisis")
    r = await route("몇 년째 혼자라 사는 게 의미가 없어요", S0, [], chat)
    assert (r.kind, r.layer, r.safety_rules) == ("crisis", 2, ["llm_guard"])


@sync
async def test_layer2_emergency_hides_no_symptom_chip():
    """2층은 과다 복용인지 알려 주지 않으므로 2층 응급은 [지금은 증상이 없어요]를 늘 숨김 (#108 리뷰 1, 10/20 수인 결정)"""
    r = await route("아까부터 좀 이상해요", S0, [], FakeChat(guard="emergency"))
    assert (r.kind, r.layer, r.overdose) == ("emergency", 2, True)
    r = await route("아까부터 좀 이상해요", S0, [], FakeChat(guard="crisis"))
    assert (r.kind, r.layer, r.overdose) == ("crisis", 2, False)


@sync
async def test_guard_and_classify_both_called():
    chat = FakeChat()
    r = await route("자몽주스 마셔도 돼요?", S0, [], chat)
    assert sorted(chat.calls) == ["classify", "guard"]
    assert r.kind == "medication"
    assert r.usage.calls == 2


@sync
async def test_guard_failure_is_error_not_answer():
    """2층이 응답하지 않으면 답을 만들지 않고 답변 오류(E6)로 (10/19 수인 결정)"""
    r = await route("자몽주스 마셔도 돼요?", S0, [], FakeChat(guard=LLMError("timeout")))
    assert r.kind == "error"


@sync
async def test_classify_failure_is_error_when_guard_none():
    r = await route("자몽주스 마셔도 돼요?", S0, [], FakeChat(classify=LLMError("timeout")))
    assert r.kind == "error"


@sync
async def test_classify_missing_field_is_error():
    """분류 결과에 필요한 칸이 빠지면 KeyError가 아니라 답변 오류(E6)로 (#108 리뷰 2)"""
    broken = classified()
    del broken["target_source"]
    r = await route("자몽주스 마셔도 돼요?", S0, [], FakeChat(classify=broken))
    assert r.kind == "error"


@sync
async def test_guard_risk_wins_even_if_classify_failed():
    r = await route("다 내려놓고 싶네요", S0, [], FakeChat(guard="crisis", classify=LLMError("timeout")))
    assert (r.kind, r.layer) == ("crisis", 2)


@sync
async def test_classify_risk_is_ignored():
    """2층 판단은 전용 호출만 따름 (분류 안의 판단은 17개 중 10개를 놓침, 10/12)"""
    chat = FakeChat(guard="none", classify=classified(risk="crisis"))
    r = await route("혈압약은 아침에 먹나요?", S0, [], chat)
    assert r.kind == "medication"


@sync
async def test_pregnancy_goes_to_refer():
    chat = FakeChat(classify=classified(category="out_of_scope"))
    r = await route("임신 중인데 이 약 먹어도 돼요?", S0, [], chat)
    assert (r.kind, r.classification["refer_kind"]) == ("refer", "next_visit")


@sync
async def test_food_chip_goes_to_medication():
    """추천 칩 "같이 먹으면 안 되는 음식"을 분류가 범위 밖으로 봐도 약 갈래로 (10/27 실제 분류 3번 중 3번 범위 밖)"""
    for q in (
        "같이 먹으면 안 되는 음식이 있나요?",
        "약이랑 함께 먹으면 안 되는 음식 있어?",
        "피해야 할 음식이 있나요?",
    ):
        r = await route(q, S0, [], FakeChat(classify=classified(category="out_of_scope")))
        assert r.kind == "medication", q


@sync
async def test_food_or_drink_question_goes_to_medication():
    """약 이름 없이 먹어도, 마셔도 되는지 물어도 먹는 약이 있으면 약 갈래로. 분류가 이유에는 약과의 상호작용이라 쓰고
    갈래는 범위 밖으로 고름 (10/29 실제 분류 4번 중 4번, #145 채연 리뷰). 근거 검색은 먹는 약 전체로 찾음"""
    for q in (
        "자몽주스 마셔도 돼요?",
        "커피 마셔도 되나요?",
        "막걸리 한잔 마셔도 괜찮아요?",
        "바나나 먹어도 돼요?",
        "홍삼 드셔도 되나요?",
        # 먹으면 안 되는지 묻는 꼴 (어르신이 흔히 쓰는 말투)
        "자몽 먹으면 안 되나요?",
        "술 마시면 안 돼요?",
        "우유랑 같이 드시면 괜찮아요?",
    ):
        r = await route(q, S0, [], FakeChat(classify=classified(category="out_of_scope")))
        assert r.kind == "medication", q
    # 먹는 약이 없으면 찾을 근거가 없어 범위 밖 그대로
    r = await route("자몽주스 마셔도 돼요?", NO_DRUGS, [], FakeChat(classify=classified(category="out_of_scope")))
    assert r.kind == "out_of_scope"
    # 먹어도 되는지 묻지 않는 범위 밖 질문, 추천을 바라는 질문은 그대로 (골든셋 O3 "아무 약이나 추천해 줘")
    for q in (
        "아무 약이나 추천해 줘",
        "같이 먹으면 되는 영양제 추천해 줘",
        "오늘 저녁 뭐 먹을까요?",
        "마이클 잭슨이 누구야?",
    ):
        r = await route(q, S0, [], FakeChat(classify=classified(category="out_of_scope")))
        assert r.kind == "out_of_scope", q


@sync
async def test_analysis_chip_asks_about_user_drugs():
    """분석 칩은 먹는 약끼리 묻는 질문으로 (분석의 경고가 있으면 점검 결과로 답함)"""
    r = await route(
        "이번 분석에서 가장 조심할 건 뭔가요?", S0, [], FakeChat(classify=classified(category="out_of_scope"))
    )
    assert r.kind == "medication" and r.classification["about_user_drugs"] is True


@sync
async def test_this_analysis_rule_keeps_classification_for_drug_questions():
    """질문에 "이번 분석"만 있으면 먹는 약끼리로 바꾸지 않음. 분석 칩처럼 가장 조심할 것을 물을 때만 (#135 채연 리뷰)"""
    r = await route("이번 분석에 나온 노바스크는 어떻게 먹어야 하나요?", S0, [], FakeChat(classify=classified()))
    assert r.kind == "medication" and r.classification["about_user_drugs"] is False


@sync
async def test_chip_rules_do_not_override_refer_or_other_questions():
    chat = FakeChat(classify=classified(category="refer", refer_kind="pharmacist"))
    assert (await route("같이 먹으면 안 되는 음식이 있나요?", S0, [], chat)).kind == "refer"
    for q in ("마이클 잭슨이 누구야?", "오늘 저녁 음식 추천해 줘", "분석이 뭐예요?"):
        r = await route(q, S0, [], FakeChat(classify=classified(category="out_of_scope")))
        assert r.kind == "out_of_scope" and not r.classification["about_user_drugs"], q


@sync
async def test_refer_passes_through():
    chat = FakeChat(classify=classified(category="refer", refer_kind="next_visit"))
    r = await route("혈압이 정상이 됐는데 약을 끊어도 되나요?", S0, [], chat)
    assert r.kind == "refer"


@sync
async def test_guess_from_memory_becomes_clarify():
    """'처음에 물어본 약'인데 기억에 없으면 되물음 (기억 밖의 약을 단정하지 않음)"""
    chat = FakeChat(classify=classified(target_drug="노바스크정5밀리그람", target_source="history"))
    r = await route("처음에 물어본 그 약은 하루에 몇 번 먹어요?", S0, [], chat)
    assert r.kind == "clarify"
    assert r.clarify_question == "앞에서 말씀하신 약이 어떤 약인지 다시 알려 주시겠어요?"


@sync
async def test_ordinal_resolved_from_history():
    history = [
        {"role": "user", "content": "리피토는 무슨 약이에요?"},
        {"role": "assistant", "content": "리피토정은 콜레스테롤을 낮추는 약이에요."},
        {"role": "user", "content": "노바스크는 언제 먹어요?"},
        {"role": "assistant", "content": "노바스크정은 아침에 처방대로 드세요."},
    ]
    chat = FakeChat(classify=classified(target_drug="노바스크정5밀리그람", target_source="history"))
    r = await route("처음에 물어본 약은 하루에 몇 번 먹어요?", S0, history, chat)
    assert r.kind == "medication"
    assert r.classification["target_drug"] == "리피토정10밀리그램"  # 코드로 찾은 순서를 따름
    assert "[지시어 풀이]" in chat.seen["classify"]


@sync
async def test_turn_numbers_with_unanswered_question_in_history():
    """앞 차례 답이 없어 기록이 홀수 개여도 차례 번호가 밀리지 않음 (#108 리뷰 3)"""
    history = []
    for i in range(1, 6):
        history.append({"role": "user", "content": f"질문{i}"})
        if i < 5:
            history.append({"role": "assistant", "content": f"답{i}"})
    chat = FakeChat()
    await route("자몽주스 마셔도 돼요?", S0, history, chat)
    assert "2. 사용자: 질문2" in chat.seen["classify"] and "5. 사용자: 질문5" in chat.seen["classify"]


@sync
async def test_about_user_drugs_is_not_clarify():
    chat = FakeChat(classify=classified(category="clarify", about_user_drugs=True))
    r = await route("이 약들 같이 먹어도 돼요?", S0, [], chat)
    assert r.kind == "medication"


@sync
async def test_clarify_without_target():
    chat = FakeChat(classify=classified(category="clarify", clarify_question="어떤 약을 말씀하시나요?"))
    r = await route("그거 먹어도 돼요?", S0, [], chat)
    assert (r.kind, r.clarify_question) == ("clarify", "어떤 약을 말씀하시나요?")


@sync
async def test_route_keeps_no_raw_text():
    """갈래 결과에는 질문 원문을 담지 않음 (1층 결과와 같은 원칙)"""
    question = "약을 한꺼번에 많이 먹었어요"
    r = await route(question, S0, [], FakeChat())
    assert question not in repr(r)


@sync
async def test_dismissed_skips_layer1_emergency_only():
    """[지금은 증상이 없어요] 뒤 다시 보낸 질문은 응급 규칙을 건너뛰고 2층과 분류로 감 (명세서 H-3 emergencyDismissed, 10/22)"""
    chat = FakeChat(guard="none")
    r = await route("약 먹고 나서 가슴이 조여요", S0, [], chat, emergency_dismissed=True)
    assert r.kind == "medication"
    assert sorted(chat.calls) == ["classify", "guard"]


@sync
async def test_dismissed_skips_layer2_emergency():
    r = await route("아까부터 좀 이상해요", S0, [], FakeChat(guard="emergency"), emergency_dismissed=True)
    assert r.kind == "medication"


@sync
async def test_dismissed_keeps_crisis_checks():
    """자해 검사는 건너뛰지 않음 (설계 메모 3-3, 4-6)"""
    r = await route("죽고 싶어요", S0, [], FakeChat(), emergency_dismissed=True)
    assert (r.kind, r.layer) == ("crisis", 1)
    r = await route("아까부터 좀 이상해요", S0, [], FakeChat(guard="crisis"), emergency_dismissed=True)
    assert (r.kind, r.layer) == ("crisis", 2)
    r = await route("사라지고 싶어서 약을 한꺼번에 먹었어요", S0, [], FakeChat(), emergency_dismissed=True)
    assert (r.kind, r.safety_types) == ("crisis", ["crisis"])
