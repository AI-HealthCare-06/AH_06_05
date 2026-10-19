"""v7 고정 설정을 지키는 시험: 프롬프트 글자(해시), 다수결, 위험주제 규칙, 고르기 해석, 소항목 묶음 넓히기"""

import hashlib

from app.services.rag import gate, prompts
from app.services.rag.chunks import Chunk, expand_group
from app.services.rag.pipeline import MAX_PICK, parse_picks

# rag_sandbox/embed_threshold/_rag_prompt_hashes.json (v7 최종시험 때의 프롬프트 sha256). 프롬프트를 바꾸면 새 질문 세트로 다시 시험해야 한다
FROZEN = {
    "SELECT_PROMPT": "611ff1003e4e19e6a3f6a56c0c3ec88affa340f81cddba1461b1171cf392c1fa",
    "ANSWER_PROMPT": "60b3b1aafa0687fec2991d79756b6ded1adb451cfbb0103270ea701f7a8baf90",
    "JUDGE_A_PROMPT": "41b62424781c57e2c3b020350f0b82cb0ec131213c10a81c76621c0ee05383e9",
    "JUDGE_B_PROMPT": "2eda7ba951ef10016d929df14b24b83c37739ceea51c13dbbe9e03716dea03bc",
    "REWRITE_PROMPT": "cf6641b94f5af181253ba543657d087ba73707806c6f1e69fc2154e4448066d6",
}


def chunk(n: int, kind: str = "drug", group: str = "g") -> Chunk:
    return Chunk(f"D:1:S{n}", kind, "1", None, "S", group, n, "제목" if n else "", f"문장{n}", "약", n)


def test_prompts_frozen() -> None:
    for name, expected in FROZEN.items():
        text = getattr(prompts, name)
        assert hashlib.sha256(text.encode("utf-8")).hexdigest() == expected, f"{name}이 시험한 글과 다릅니다"


def v(a: str = "ENOUGH", b: str = "ENOUGH", direct: bool = True, c: str = "FULL") -> gate.Verdicts:
    return gate.Verdicts(a=a, b=b, b_direct=direct, c=c)


def test_majority_needs_two_of_three() -> None:
    q = "아침에 먹어도 되나요?"
    assert gate.decide(q, v()) is None
    assert gate.decide(q, v(a="PARTIAL", b="INSUFFICIENT", c="PARTIAL")) is None  # 2개 통과
    assert gate.decide(q, v(a="ENOUGH", b="INSUFFICIENT", c="NONE")) == "insufficient"  # 1개
    assert gate.decide(q, gate.EMPTY) == "insufficient"
    assert gate.decide(q, v(a="?", b="?", c="?")) == "insufficient"  # 해석 못 한 답은 통과 아님


def test_risk_topic_needs_two_full() -> None:
    risky = "약을 그냥 끊어도 되나요?"
    assert gate.is_risky(risky)
    assert gate.decide(risky, v()) is None
    # 셋 다 통과지만 완전은 1개(C만 FULL) -> 막힘
    assert gate.decide(risky, v(a="PARTIAL", b="PARTIAL", direct=False, c="FULL")) == "risk_blocked"
    # B는 ENOUGH여도 direct가 아니면 완전이 아님
    assert gate.decide(risky, v(a="PARTIAL", b="ENOUGH", direct=False, c="FULL")) == "risk_blocked"
    assert gate.decide(risky, v(a="ENOUGH", b="PARTIAL", direct=False, c="FULL")) is None
    assert not gate.is_risky("식후에 드세요?")


def test_parse_handles_garbage() -> None:
    assert gate.parse('앞말 {"verdict": "ENOUGH"} 뒷말') == {"verdict": "ENOUGH"}
    assert gate.parse("json 아님") is None
    assert gate.parse("{깨진") is None
    assert gate.parse("[1, 2]") is None


def test_parse_picks_limits_and_filters() -> None:
    cands = [chunk(i) for i in range(1, 13)]
    got = parse_picks('{"ids":[3,1,99,0,true,"2",5,6,7,8,9,10,11]}', cands, MAX_PICK)
    assert [c.seq for c in got] == [3, 1, 5, 6, 7, 8, 9, 10]  # 범위 밖, 불리언, 글자는 버리고 8개까지
    assert parse_picks("아무 말", cands, MAX_PICK) == []
    assert parse_picks('{"ids": "3"}', cands, MAX_PICK) == []
    assert parse_picks('{"ids":[]}', cands, MAX_PICK) == []


def test_expand_group_small_group_returns_all() -> None:
    group = [chunk(i) for i in range(5)]
    assert expand_group(group[3], group) == group


def test_expand_group_cap_keeps_first_sentence() -> None:
    group = [chunk(i) for i in range(20)]
    out = expand_group(group[15], group)
    assert len(out) == 8
    assert out[0].seq == 0  # 소항목 첫 문장은 항상 포함
    assert 15 in [c.seq for c in out]
    near = expand_group(group[2], group)
    assert len(near) == 8 and near[0].seq == 0 and 2 in [c.seq for c in near]


def test_expand_group_non_drug_is_itself() -> None:
    fact = chunk(1, kind="fact")
    assert expand_group(fact, [fact, chunk(2, kind="fact")]) == [fact]
