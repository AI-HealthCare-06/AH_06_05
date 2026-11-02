"""외부 모델이 쓴 합성 문장 40개를 1층 규칙과 문맥 파악만으로 확인 (AI 없음). 합격 기준이 아니라 지금 상태를 고정해 두는 시험"""

from app.services.chatbot import context_check, safety_rules
from app.tests.chatbot.extra_sentences import EXTRA


def _blocked(text: str) -> bool:
    rule = safety_rules.check(text)
    return rule.hit and context_check.looks_normal(text, rule) is None


def test_extra_counts():
    assert len(EXTRA) == 40
    assert [sum(1 for _, label, _ in EXTRA if label == k) for k in ("emergency", "crisis", "none")] == [10, 10, 20]
