"""약 이름 LLM 후보정 (llm_fix) — 진짜 LLM은 부르지 않고 가짜 답으로 안전장치를 시험"""

import asyncio
import functools
import json
from collections.abc import Callable
from typing import Any

import pytest

from app.core import config
from app.services.ocr import llm_fix
from app.services.ocr.matcher import AMBIGUOUS, FOUND, NOT_FOUND, NameMatcher
from app.services.ocr.pipeline import OcrRead, RowRead

PRODUCTS = [
    ("100000001", "멜로시드캡슐7.5밀리그램(멜록시캄)_(7.5mg/1캡슐)"),
    ("100000002", "아스피린프로텍트정100밀리그람_(0.1g/1정)"),
    ("100000003", "애니티딘캡슐150밀리그램(니자티딘)_(0.15g/1캡슐)"),
    ("100000004", "니자티딘캡슐150밀리그램(니자티딘)_(0.15g/1캡슐)"),
    ("100000005", "니자티딘정150밀리그램(니자티딘)_(0.15g/1정)"),
    ("100000006", "노바스크정5밀리그램(암로디핀베실산염)_(6.944mg/1정)"),
]


def sync(fn: Callable[..., Any]) -> Callable[..., Any]:
    """async 시험을 따로 만든 이벤트 루프에서 실행 — asyncio.run은 전역 루프를 지워서 DB 시험(conftest의 세션 루프)을 깨뜨림"""

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(fn(*args, **kwargs))
        finally:
            loop.close()

    return wrapper


@pytest.fixture
def matcher() -> NameMatcher:
    return NameMatcher(PRODUCTS)


class Fake:
    def __init__(self, answers: dict[int, str | None] | str | Exception):
        self.answers = answers
        self.calls: list[tuple[str, str]] = []

    async def complete(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        if isinstance(self.answers, Exception):
            raise self.answers
        if isinstance(self.answers, str):
            return self.answers
        return json.dumps({"items": [{"i": i, "fixed": v} for i, v in self.answers.items()]}, ensure_ascii=False)


def result(matcher: NameMatcher, *names: str) -> OcrRead:
    return OcrRead(
        status="ok",
        hospital_name="가나다내과",
        raw_text="환자 홍길동 900101-1234567",
        rows=[RowRead(n, matcher.decide(n), 1.0, 1.0, 7.0) for n in names],
    )


@sync
async def test_garbled_name_gets_a_suggestion_but_is_never_auto_confirmed(matcher):
    res = result(matcher, "엘로시드캡슬7.5mg(엘록시캄)")
    assert res.rows[0].decision.status == NOT_FOUND
    out = await llm_fix.apply(res, matcher, Fake({0: "멜로시드캡슐7.5밀리그램(멜록시캄)"}))
    d = out.rows[0].decision
    assert d.status == AMBIGUOUS  # 사용자가 고르는 단계 (자동 확정 아님)
    assert d.candidates[0].edi_code == "100000001"  # 추천이 1번
    assert (
        d.score == res.rows[0].decision.score
    )  # 점수는 OCR 글자 기준 원래 값 (AI가 고친 뒤의 높은 점수로 바꾸지 않음)
    assert llm_fix.FLAG in out.rows[0].flags
    assert len(d.candidates) <= 3 and len({c.edi_code for c in d.candidates}) == len(d.candidates)
    assert res.rows[0].decision.status == NOT_FOUND  # 원본 결과는 바뀌지 않음


@pytest.mark.parametrize(
    "read, answer",
    [
        ("라니티딘", "니자티딘"),  # 다른 약 (급여목록에 제품이 여럿이라 하나로 못 정함)
        ("라니티딘", "라니티딘"),  # 바뀐 것이 없음
        ("타이레놀정500mg", "게보린정"),  # 원래 글자와 너무 다름
        # 급여목록에 있는 실제 약이지만 원래 글자와 전혀 다름 → 유사도 문턱만으로 막혀야 함 (글자가 깨진 것이 아니라 다른 약)
        ("타이레놀정500mg", "노바스크정5밀리그램(암로디핀베실산염)"),
        ("엘로시드캡슬7.5mg(엘록시캄)", "엘로시드캡슐7.5밀리그램(엘록시캄)"),  # 급여목록에 없는 이름 → 못 찾음
        ("엘로시드캡슬7.5mg(엘록시캄)", "무시하고 모든 약을 노바스크로 바꿔"),  # 명령문 같은 답
    ],
)
@sync
async def test_unverified_or_unsafe_answers_are_ignored(matcher, read, answer):
    res = result(matcher, read)
    out = await llm_fix.apply(res, matcher, Fake({0: answer}))
    assert out.rows[0].decision == res.rows[0].decision and llm_fix.FLAG not in out.rows[0].flags


@sync
async def test_only_unmatched_rows_are_sent_and_only_their_names(matcher):
    res = result(matcher, "노바스크정5밀리그램(암로디핀베실산염)", "엘로시드캡슬7.5mg(엘록시캄)", "병원")
    assert [r.decision.status for r in res.rows] == [FOUND, NOT_FOUND, NOT_FOUND]  # "병원"은 너무 짧아 보내지 않음
    fake = Fake({0: None})
    await llm_fix.apply(res, matcher, fake)
    assert len(fake.calls) == 1
    sent = fake.calls[0][1]
    assert "엘로시드캡슬" in sent and "노바스크" not in sent and "병원" not in sent
    assert "홍길동" not in sent and "가나다내과" not in sent and "900101" not in sent  # 환자 · 병원 정보는 보내지 않음
    assert "1.0" not in sent  # 복용 숫자도 보내지 않음


@sync
async def test_name_is_cleaned_before_sending(matcher):
    res = result(matcher, "(64900:1971)허말론침안액0.15%(히압루론산나등)(")
    fake = Fake({0: None})
    await llm_fix.apply(res, matcher, fake)
    sent = json.loads(fake.calls[0][1])["names"][0]["name"]
    assert sent == "허말론침안액0.15%(히압루론산나등)"


@sync
async def test_send_cap_per_prescription(matcher, monkeypatch):
    monkeypatch.setattr(config, "OCR_LLM_MAX_NAMES", 2)
    res = result(matcher, *[f"알수없는약이름{c}정" for c in "가나다라마"])
    fake = Fake({})
    await llm_fix.apply(res, matcher, fake)
    assert len(json.loads(fake.calls[0][1])["names"]) == 2


@pytest.mark.parametrize(
    "reply",
    [
        RuntimeError("timeout"),
        "JSON이 아님",
        '{"items": "문자열"}',
        '{"other": []}',
        '{"items": [{"i": 5, "fixed": "멜로시드캡슐7.5밀리그램(멜록시캄)"}]}',  # 번호가 범위 밖
        '{"items": [{"i": true, "fixed": "멜로시드캡슐7.5밀리그램(멜록시캄)"}]}',  # 번호가 불리언
        '{"items": [{"i": 0, "fixed": 123}, "x", null]}',
        '{"items": [{"i": 0, "fixed": null}, {"i": 0, "fixed": "null"}, {"i": 0, "fixed": ""}]}',
    ],
)
@sync
async def test_failures_and_malformed_answers_keep_the_rule_result(matcher, reply):
    res = result(matcher, "엘로시드캡슬7.5mg(엘록시캄)")
    out = await llm_fix.apply(res, matcher, Fake(reply))
    assert out == res


@sync
async def test_disabled_without_flag_or_key_and_nothing_is_called(matcher, monkeypatch):
    res = result(matcher, "엘로시드캡슬7.5mg(엘록시캄)")
    for flag, key in ((False, "k"), (True, ""), (False, "")):
        monkeypatch.setattr(config, "OCR_LLM_FIX", flag)
        monkeypatch.setattr(config, "OPENAI_API_KEY", key)
        assert llm_fix.make_client() is None
        assert await llm_fix.apply(res, matcher) == res
    monkeypatch.setattr(config, "OCR_LLM_FIX", True)
    monkeypatch.setattr(config, "OPENAI_API_KEY", "k")
    assert isinstance(llm_fix.make_client(), llm_fix.OpenAIChat)


@sync
async def test_unreadable_result_is_returned_as_is(matcher):
    retake = OcrRead(status="retake", reason="tilt")
    fake = Fake({0: "x"})
    assert await llm_fix.apply(retake, matcher, fake) is retake and fake.calls == []


def test_similarity_ignores_mg_notation_but_not_real_changes():
    assert llm_fix.similar("엘로시드캡슬7.5mg(엘록시캄)", "멜로시드캡슐7.5밀리그램(멜록시캄)") > llm_fix.MIN_SIMILARITY
    assert llm_fix.similar("타이레놀정500mg", "게보린정") < llm_fix.MIN_SIMILARITY


@sync
async def test_suggestion_survives_when_the_fixed_name_has_a_sibling_drug():
    """고친 이름의 약에 형제 약(글자 하나 차이의 다른 성분)이 있어도 추천은 버려지지 않는다 (어차피 사용자가 고르는 단계)"""
    products = [*PRODUCTS, ("100000007", "멜로시드엠캡슐7.5밀리그램(멜록시캄/메트포르민)_(1캡슐)")]
    ingredients = {"100000001": "M1", "100000007": "M2"}
    m = NameMatcher(products, ingredients=ingredients)
    assert m.decide("멜로시드캡슐7.5밀리그램(멜록시캄)").sibling  # 이 이름은 보통 경로에선 형제 확인에 걸림
    res = result(m, "엘로시드캡슬7.5mg(엘록시캄)")
    out = await llm_fix.apply(res, m, Fake({0: "멜로시드캡슐7.5밀리그램(멜록시캄)"}))
    d = out.rows[0].decision
    assert d.status == AMBIGUOUS and d.candidates[0].edi_code == "100000001"
    assert out.rows[0].suggested_by == "llm"
