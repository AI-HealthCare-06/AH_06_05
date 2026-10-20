"""대화 맥락 준비 (#99, 설계 메모 7-11). 고정 정보, 최근 N번, 지시어 풀이 (AI 없음).

로컬 실험(10/12 ~ 10/13 대화 기억 실험)에서 고른 방식: 최근 4번 주고받은 대화 + "처음에 물어본 약" 같은 말은
코드가 저장된 전체 대화에서 찾음 (AI 기억에 기대지 않음). 사실 칸과 요약은 #99 PR 2에서 옮긴다.
"""

import re
from dataclasses import dataclass, field

RECENT_TURNS = 4  # 실험에서 고른 값: 20차례 넘는 대화에서 잘못 단정 0


@dataclass
class UserDrug:
    """지금 먹는 약 하나 (처방 기록에서 옴)"""

    name: str  # 제품 이름 (예: 노바스크정5밀리그람)
    ingredient: str
    purpose: str  # 쓰임 (예: 혈압)
    how: str  # 처방대로 먹는 법 (예: 1일 1회 아침)
    code: str = ""  # 약 코드 (근거 검색 범위, 급여목록 ediCode 또는 품목기준코드)


@dataclass
class FixedInfo:
    """답을 만들 때 늘 넣는 고정 정보 (먹는 약, 진단받은 질환, 나이)"""

    age: int | None
    diseases: list[str] = field(default_factory=list)  # 질환 이름 (예: 고혈압)
    # 근거 검색 범위의 질환 (팩트표 질환 id, 예: HTN). 처방전 질환과 내 정보 질환을 합친 것 (#101, 10/20)
    disease_ids: list[str] = field(default_factory=list)
    drugs: list[UserDrug] = field(default_factory=list)


def fixed_info_text(info: FixedInfo) -> str:
    drugs = "\n".join(f"- {d.name} ({d.ingredient}, {d.purpose}) {d.how}" for d in info.drugs) or "- 처방 약 없음"
    age = f"나이 {info.age}세\n" if info.age is not None else ""
    return f"{age}진단받은 질환: {', '.join(info.diseases) or '없음'}\n지금 먹는 약 (처방대로)\n{drugs}"


def recent(history: list[dict[str, str]], n: int = RECENT_TURNS) -> list[dict[str, str]]:
    """최근 N번 주고받은 대화 (사용자 질문 N개와 그 답). N=0이면 대화 기록 없이"""
    return history[-2 * n :] if n > 0 else []


def dialogue(messages: list[dict[str, str]], first_turn: int = 1) -> str:
    """앞 대화를 읽는 모양으로. 차례 번호는 대화 처음부터 센 번호 ("처음에 물어본", "두 번째로"를 풀 수 있게)"""
    lines, turn = [], first_turn - 1
    for m in messages:
        if m["role"] == "user":
            turn += 1
            lines.append(f"{turn}. 사용자: {m['content']}")
        else:
            lines.append(f"   챗봇: {m['content']}")
    return "\n".join(lines)


def drug_keys(drug: UserDrug) -> list[str]:
    """약을 가리키는 말: 제품 이름 앞부분, 성분, 쓰임("혈압약")"""
    keys = [drug.name[:3], drug.ingredient]
    for word in ("혈압", "당뇨", "콜레스테롤"):
        if word in drug.purpose:
            keys.append(word)
    return keys


def find_drug(text: str, drugs: list[UserDrug]) -> UserDrug | None:
    hits = [d for d in drugs if any(k in text for k in drug_keys(d))]
    return hits[0] if len(hits) == 1 else None


_ORDINAL = [(r"(맨\s*처음|제일\s*처음|처음에?|첫\s*번째)", 1), (r"두\s*번째", 2), (r"세\s*번째", 3)]
_ASKED = r"(물어본|물어봤던|얘기한|말한)"
_STOP = {
    "물어본",
    "물어봤던",
    "얘기한",
    "말한",
    "아까",
    "그거",
    "그약",
    "약은",
    "약이요",
    "하루에",
    "몇번",
    "먹어요",
    "먹는",
    "거",
    "맞죠",
}


def resolve_ordinal(question: str, history: list[dict[str, str]], drugs: list[UserDrug]) -> str | None:
    """ "처음에 물어본 약", "두 번째로 물어본 약"을 저장된 전체 대화에서 코드로 찾음"""
    if not re.search(_ASKED, question):
        return None
    k = next((n for pat, n in _ORDINAL if re.search(pat, question)), None)
    if not k:
        return resolve_topic(question, history, drugs)
    asked: list[str] = []
    for m in history:
        if m["role"] == "user":
            d = find_drug(m["content"], drugs)
            if d and d.name not in asked:
                asked.append(d.name)
    return asked[k - 1] if len(asked) >= k else None


def resolve_topic(question: str, history: list[dict[str, str]], drugs: list[UserDrug]) -> str | None:
    """ "자몽 물어봤던 그 약"처럼 주제로 가리키면, 그 주제를 물었던 사용자 질문의 약을 찾음"""
    found = re.search(r"([가-힣]{1,5})\s*(?:을|를|이|가)?\s*" + _ASKED, question)
    topic = found.group(1) if found and found.group(1) not in _STOP else None
    if not topic:
        return None
    # 차례마다 그때 이야기하던 약을 기억해 둠 ("그 약 먹으면서 술 마셔도 돼요?"는 바로 앞에서 말한 약)
    current, by_turn = None, []
    for m in history:
        if m["role"] == "user":
            d = find_drug(m["content"], drugs)
            current = d.name if d else current
            by_turn.append((m["content"], current))
    for content, drug_name in reversed(by_turn):
        if topic in content and drug_name:
            return drug_name
    return None


def target_in_memory(target: str, past: list[dict[str, str]], summary: str | None, drugs: list[UserDrug]) -> bool:
    """분류기가 '앞 대화에서 찾았다'고 한 약이 정말 앞 대화나 요약에 있는지 코드로 확인"""
    drug = next((d for d in drugs if d.name[:3] in target or d.ingredient in target), None)
    if not drug:
        return False
    # 이름과 성분은 앞 대화 전체와 요약에서, 쓰임("혈압약")은 사용자 질문에서만 찾음 (답에는 "혈압"이 흔히 나와서)
    names = [drug.name[:3], drug.ingredient]
    memory = " ".join(m["content"] for m in past) + " " + (summary or "")
    user_text = " ".join(m["content"] for m in past if m["role"] == "user")
    return any(k in memory for k in names) or any(k in user_text for k in drug_keys(drug)[2:])
