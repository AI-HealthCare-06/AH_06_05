"""대화 기억 도우미 시험 (#99 PR 1). 최근 N번, 차례 번호, 지시어 풀이 (AI 없음)."""

from app.services.chatbot.context import (
    FixedInfo,
    UserDrug,
    dialogue,
    fixed_info_text,
    recent,
    resolve_ordinal,
    target_in_memory,
)

DRUGS = [
    UserDrug("노바스크정5밀리그람", "암로디핀", "혈압", "1일 1회 아침"),
    UserDrug("리피토정10밀리그램", "아토르바스타틴", "콜레스테롤", "1일 1회 저녁"),
]

HISTORY = [
    {"role": "user", "content": "리피토는 무슨 약이에요?"},
    {"role": "assistant", "content": "콜레스테롤을 낮추는 약이에요."},
    {"role": "user", "content": "자몽주스랑 노바스크 같이 먹어도 돼요?"},
    {"role": "assistant", "content": "약사에게 확인해 주세요."},
    {"role": "user", "content": "술은요?"},
    {"role": "assistant", "content": "술은 줄여 주세요."},
]


def test_recent_keeps_last_n_turns():
    assert recent(HISTORY, 2) == HISTORY[-4:]
    assert recent(HISTORY, 0) == []


def test_dialogue_numbers_turns_from_start():
    text = dialogue(recent(HISTORY, 2), first_turn=2)
    assert text.splitlines()[0] == "2. 사용자: 자몽주스랑 노바스크 같이 먹어도 돼요?"
    assert "3. 사용자: 술은요?" in text


def test_resolve_ordinal_first_and_second():
    assert resolve_ordinal("처음에 물어본 약은 언제 먹어요?", HISTORY, DRUGS) == "리피토정10밀리그램"
    assert resolve_ordinal("두 번째로 물어본 약은요?", HISTORY, DRUGS) == "노바스크정5밀리그람"


def test_resolve_by_topic():
    assert resolve_ordinal("자몽 물어봤던 그 약은 아침에 먹어요?", HISTORY, DRUGS) == "노바스크정5밀리그람"


def test_resolve_needs_asking_word():
    assert resolve_ordinal("처음 먹는 약이에요", HISTORY, DRUGS) is None


def test_target_in_memory():
    assert target_in_memory("리피토정10밀리그램", HISTORY, None, DRUGS)
    assert not target_in_memory("리피토정10밀리그램", [], None, DRUGS)
    assert target_in_memory("리피토정10밀리그램", [], "리피토 이야기를 함", DRUGS)


def test_fixed_info_text():
    text = fixed_info_text(FixedInfo(age=72, diseases=["고혈압"], drugs=DRUGS))
    assert "나이 72세" in text
    assert "진단받은 질환: 고혈압" in text
    assert "- 노바스크정5밀리그람 (암로디핀, 혈압) 1일 1회 아침" in text
    assert "처방 약 없음" in fixed_info_text(FixedInfo(age=None, diseases=[], drugs=[]))
