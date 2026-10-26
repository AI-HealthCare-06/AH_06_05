"""1층에 더하는 Jev 판단 시험 (10/26 수인 결정). TypeSafe는 부르지 않고 가짜 판단으로 흐름만 확인 (CI에서 부르지 않음)."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from unittest.mock import patch

import pytest

from app.core import config
from app.services.chatbot import jev
from app.services.chatbot.pipeline import screen
from app.tests.chatbot.test_route import sync

ON = {"SAFETY_JEV": True, "TYPESAFE_API_KEY": "test-key", "SAFETY_JEV_TIMEOUT_SEC": 1.0, "SAFETY_JEV_MAX_NONE": 0.3}
NORMAL = "요즘 사는 게 다 귀찮네요"  # 1층 규칙에 걸리지 않는 문장


def fake(choice: str, p_none: float, calls: list[str]) -> Callable[[str], Awaitable[tuple[str, float]]]:
    async def judge(question: str) -> tuple[str, float]:
        calls.append(question)
        return choice, p_none

    return judge


async def run(text: str, judge: Callable[[str], Awaitable[tuple[str, float]]], dismissed: bool = False, **cfg: object):
    with patch.multiple(config, **{**ON, **cfg}), patch.object(jev, "_typesafe", judge):
        return await screen(text, dismissed)


@sync
async def test_rule_hit_does_not_call_jev():
    calls: list[str] = []
    r = await run("약 먹고 나서 가슴이 조여요", fake("none", 0.9, calls))
    assert r is not None and r.layer == 1 and "jev" not in r.safety_rules
    assert calls == []


@sync
async def test_context_release_does_not_call_jev():
    """문맥 파악이 정상으로 푼 문장은 Jev가 다시 막지 않음"""
    calls: list[str] = []
    assert await run("드라마에서 쓰러지는 장면을 봤는데 저혈당이 그런가요?", fake("emergency", 0.0, calls)) is None
    assert calls == []


@sync
async def test_jev_blocks_only_when_confident():
    calls: list[str] = []
    r = await run(NORMAL, fake("crisis", 0.1, calls))
    assert r is not None and (r.kind, r.layer, r.safety_types, r.safety_rules) == ("crisis", 1, ["crisis"], ["jev"])
    assert calls == [NORMAL]
    assert await run(NORMAL, fake("crisis", 0.3, [])) is None  # "해당 없음" 확률이 기준 이상이면 통과
    assert await run(NORMAL, fake("none", 0.05, [])) is None


@sync
async def test_jev_emergency_hides_no_symptom_chip():
    """Jev는 과다 복용인지 알려 주지 않으므로 2층처럼 [지금은 증상이 없어요]를 늘 숨김 (10/20 2층 결정과 같게)"""
    r = await run(NORMAL, fake("emergency", 0.05, []))
    assert r is not None and r.kind == "emergency" and r.overdose is True


@sync
async def test_dismissed_resend_checks_crisis_only():
    assert await run(NORMAL, fake("emergency", 0.05, []), dismissed=True) is None
    r = await run(NORMAL, fake("crisis", 0.05, []), dismissed=True)
    assert r is not None and r.kind == "crisis"


@sync
async def test_off_or_no_key_does_not_call_jev():
    calls: list[str] = []
    assert await run(NORMAL, fake("crisis", 0.0, calls), SAFETY_JEV=False) is None
    assert await run(NORMAL, fake("crisis", 0.0, calls), TYPESAFE_API_KEY="") is None
    assert calls == []


@sync
async def test_slow_or_failing_jev_falls_back_to_rules(caplog: pytest.LogCaptureFixture):
    """1층은 AI 없이도 돌아야 함: 늦거나 실패하면 규칙 결과만 쓰고 로그를 남김 (질문 글은 남기지 않음)"""

    async def slow(question: str) -> tuple[str, float]:
        await asyncio.sleep(1)
        return "crisis", 0.0

    async def broken(question: str) -> tuple[str, float]:
        raise RuntimeError("down")

    with caplog.at_level(logging.WARNING):
        assert await run(NORMAL, slow, SAFETY_JEV_TIMEOUT_SEC=0.05) is None
        assert await run(NORMAL, broken) is None
    assert "Jev" in caplog.text and NORMAL not in caplog.text
