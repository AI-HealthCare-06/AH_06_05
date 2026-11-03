"""골든셋 LLM 채점 (scripts/chatbot/run_golden.py --judge). 가짜 AI로 묻는 내용과 읽는 방법만 확인 (CI에서 OpenAI를 부르지 않음)"""

import importlib.util
import sys
from pathlib import Path
from typing import Any

from app.services.chatbot.llm import Usage
from app.tests.chatbot.test_route import sync

_PATH = Path(__file__).resolve().parents[3] / "scripts" / "chatbot" / "run_golden.py"
_spec = importlib.util.spec_from_file_location("run_golden", _PATH)
assert _spec and _spec.loader
golden = importlib.util.module_from_spec(_spec)
sys.modules["run_golden"] = golden
_spec.loader.exec_module(golden)


class FakeJudge:
    def __init__(self, result: dict[str, Any]):
        self.result = result
        self.seen: list[str] = []

    async def complete_json(
        self, system: str, messages: list[dict[str, str]], schema: dict[str, Any], name: str, usage: Usage
    ) -> dict[str, Any]:
        self.seen.append(messages[-1]["content"])
        usage.calls += 1
        return self.result


def _item(item_id: str):
    return next(it for it in golden.ITEMS if it.id == item_id)


def test_every_text_item_has_must_and_forbidden_from_golden_set():
    """글로 답하는 문항은 골든셋 3절의 꼭 들어갈 것, 들어가면 안 될 것을 가짐. 응급, 자해(U1, K1)는 화면 카드라 규칙으로만 봄"""
    for it in golden.ITEMS:
        if it.id in ("U1", "K1"):
            assert not it.must and not it.forbidden, it.id
        else:
            assert it.must and it.forbidden, it.id


@sync
async def test_judge_sends_question_answer_and_rules_and_reads_result():
    fake = FakeJudge(
        {
            "must": [{"ok": True, "why": "의사와 상의하라고 함"}],
            "forbidden": [
                {"hit": False, "quote": "", "why": "끊어도 된다는 말 없음"},
                {"hit": False, "quote": "", "why": "없음"},
            ],
        }
    )
    it = _item("R1")
    v = await golden.judge(it, "약을 끊는 것은 의사와 상의해 주세요.", fake, Usage())
    sent = fake.seen[0]
    assert it.question in sent and "약을 끊는 것은 의사와 상의해 주세요." in sent
    assert all(m in sent for m in it.must) and all(f in sent for f in it.forbidden)
    assert v.passed and v.summary == "꼭 1/1, 금지 0/2"


@sync
async def test_judge_fails_on_forbidden_or_missing_and_on_bad_shape():
    it = _item("R1")
    bad = FakeJudge(
        {
            "must": [{"ok": True, "why": ""}],
            "forbidden": [
                {"hit": True, "quote": "끊어도 돼요", "why": "허용함"},
                {"hit": False, "quote": "", "why": ""},
            ],
        }
    )
    v = await golden.judge(it, "이제 끊어도 돼요.", bad, Usage())
    assert not v.passed and v.summary == "꼭 1/1, 금지 1/2" and v.notes == ['금지 걸림: "끊어도 돼요" (끊어도 돼요)']
    broken = FakeJudge({"must": [{"ok": True, "why": ""}], "forbidden": [{"hit": True, "why": "끊어도 돼요"}, {}]})
    assert (await golden.judge(it, "끊어도 돼요.", broken, Usage())).summary == "채점 실패"  # hit가 없는 항목
    short = FakeJudge({"must": [], "forbidden": []})  # 항목 수가 다르면 채점 실패로 봄 (통과로 세지 않음)
    v = await golden.judge(it, "답", short, Usage())
    assert not v.passed and v.summary == "채점 실패"


@sync
async def test_forbidden_hit_counts_only_when_the_quote_is_really_in_the_answer():
    """채점 AI가 hit=true라면서 답에 없는 말을 적으면 걸림이 아니라 불확실로 셈 (11/3 실제 채점에서 5문항이 이랬음).
    띄어쓰기와 따옴표 차이는 같은 글로 봄"""
    it = _item("R1")
    unsure = FakeJudge(
        {
            "must": [{"ok": True, "why": ""}],
            "forbidden": [
                {"hit": True, "quote": "", "why": "답변에 '끊어도 돼요'라는 표현이 없다"},
                {"hit": True, "quote": "조금씩 줄여 보세요", "why": "줄이는 방법"},
            ],
        }
    )
    v = await golden.judge(it, '의사와 상의해 주세요. "조금씩  줄여 보세요"라고는 하지 않을게요.', unsure, Usage())
    assert not v.passed and v.summary == "꼭 1/1, 금지 1/2, 불확실 1"
    assert v.notes[0].startswith("금지 걸림: 줄이는 방법 제시") and v.notes[1].startswith("금지 채점 불확실")


@sync
async def test_card_answers_are_not_judged():
    fake = FakeJudge({})
    v = await golden.judge(_item("U1"), None, fake, Usage())
    assert v is None and not fake.seen
