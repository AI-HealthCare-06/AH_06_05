"""판정 3가지(A, B, C)를 읽고 다수결과 위험주제 규칙으로 통과를 가른다 (eval_v7.py mk()와 같은 규칙, v7 고정 설정).

통과 = 3가지 중 2개 이상이 통과(A, B는 ENOUGH 또는 PARTIAL, C는 FULL 또는 PARTIAL).
위험주제(중단, 빼먹음, 두 배, 수술이나 검사 전 등)는 3가지 중 2개 이상이 "완전"일 때만 통과
(A는 ENOUGH, B는 ENOUGH이면서 direct, C는 FULL).
"""

import json
import re
from dataclasses import dataclass
from typing import Any

RISK = re.compile(
    r"(끊어|끊어도|끊고|끊으|중단|그만\s*먹|안\s*먹어도|안 먹|먹지\s*않|깜빡|까먹|잊어|잊었|빼먹|빠뜨|거르|두\s*알|두\s*배|한꺼번에|몰아서|2배|수술|시술|검사\s*전|검진\s*전|계속\s*먹어야|계속\s*복용|계속\s*드)"
)
OK_VERDICTS = ("ENOUGH", "PARTIAL")
OK_TYPES = ("FULL", "PARTIAL")


def is_risky(question: str) -> bool:
    return bool(RISK.search(question))


def parse(answer: str) -> dict[str, Any] | None:
    """LLM 답에서 JSON 한 덩어리를 꺼낸다 (v6_run.parse와 같음)"""
    m = re.search(r"\{.*\}", answer, re.S)
    try:
        data = json.loads(m.group(0)) if m else None
    except Exception:
        return None
    return data if isinstance(data, dict) else None


@dataclass(frozen=True)
class Verdicts:
    a: str  # ENOUGH / PARTIAL / INSUFFICIENT / ?
    b: str
    b_direct: bool
    c: str  # FULL / PARTIAL / NONE / ?

    @property
    def passes(self) -> tuple[bool, bool, bool]:
        return (self.a in OK_VERDICTS, self.b in OK_VERDICTS, self.c in OK_TYPES)

    @property
    def fulls(self) -> tuple[bool, bool, bool]:
        return (self.a == "ENOUGH", self.b == "ENOUGH" and self.b_direct, self.c == "FULL")


EMPTY = Verdicts(a="INSUFFICIENT", b="INSUFFICIENT", b_direct=False, c="NONE")


def decide(question: str, v: Verdicts) -> str | None:
    """통과면 None, 막히면 이유(insufficient 또는 risk_blocked)"""
    if sum(v.passes) < 2:
        return "insufficient"
    if is_risky(question) and sum(v.fulls) < 2:
        return "risk_blocked"
    return None
