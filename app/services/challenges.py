"""실천 목표 추천 규칙 (REQ-110, 화면 RG-05 → RW-02). AI 없음, 팩트표(guide/data/lifestyle_facts.json)에 근거가 있을 때만.

- 챌린지는 9/23에 정한 세 가지만: 국물 남기기, 빠르게 걷기 30분, 술 마시지 않기 ("물 6잔"은 심부전, 신장병에 위험해 뺌)
- 질환은 분석의 질환(처방전, 내 정보, 질환 직접 선택)만 봄. 생활습관 탭과 같은 기준이라 약 링크도 그 질환 아래에서만 찾음
- 질환이 없으면 약을 먹어도 추천하지 않음. 팩트표는 질환별이고 약 링크도 질환 아래에 있어, 생활습관 탭과 같은 기준을 씀 (10/30 수인 결정)
- 허혈성심질환은 운동을 의료진이 정한 강도로 하라고 해서, 다른 질환이 걷기를 권해도 그 모양으로 바꿈 (10/30 수인 결정)
- 술은 금주까지 말하는 근거만 (고혈압 "절주"는 아님). 내 정보 음주가 "안 마심"이면 뺌 (10/30 수인 결정)
"""

import re
from dataclasses import dataclass, field
from typing import Any

from app.services.guide import lifestyle

DRUG_REASON = "약과 함께"
# "의료진 확인"은 목표로 만들지 않는 항목의 라벨이라(#43, 명세서 R-4 requiresClinician) 고를 수 있는 걷기에는 다른 말을 씀
HEART_LABEL = "의료진이 정한 강도로"


@dataclass(frozen=True)
class Source:
    """팩트표 근거 한 줄. category가 있으면 그 질환의 생활습관 항목, drug가 있으면 그 질환의 약 링크(약 종류 이름 일부)"""

    disease: str  # 팩트표 질환 id (HTN 등)
    category: str | None = None
    desc: str | None = None  # 설명으로 쓸 팩트표 글을 고르는 정규식. 없으면 항목 목표(goal) 그대로
    drug: str | None = None


@dataclass(frozen=True)
class Challenge:
    key: str
    title: str
    goal_type: str  # check / quantity
    sources: tuple[Source, ...]
    target_value: int | None = None
    unit: str | None = None
    skip_drinking: tuple[str, ...] = field(default=())  # 내 정보 음주가 이 값이면 추천하지 않음


CHALLENGES: tuple[Challenge, ...] = (
    Challenge(
        "soup",
        "국물 남기기",
        "check",
        (Source("HTN", "나트륨 줄이기"), Source("CKD", "나트륨 제한")),
    ),
    Challenge(
        "walk",
        "빠르게 걷기 30분",
        "quantity",
        (
            Source("HTN", "유산소 운동"),
            Source("DLP", "운동"),
            Source("DM2", "운동"),
            Source("OP", "체중부하 운동"),
            Source("COPD", "호흡 재활", desc=r"걷기"),
            Source("IHD", "심장재활 운동"),
        ),
        target_value=30,
        unit="분",
    ),
    Challenge(
        "alcohol",
        "술 마시지 않기",
        "check",
        (
            Source("STROKE", "금연·절주", desc=r"금주"),
            Source("DLP", "중성지방 관리", desc=r"금주"),
            Source("DM2", drug="설포닐우레아", desc=r"음주"),
            Source("OA", drug="아세트아미노펜", desc=r"음주"),
        ),
        skip_drinking=("none",),
    ),
)
# 허혈성심질환이 있으면 걷기를 이 모양으로 (팩트표 "심장재활 운동": 의료진이 정한 강도로 주 5회).
# 라벨에 강도가 있어 제목은 "걷기"만, 설명에는 팩트표의 의료진 승인 문장도 붙임 (REQ-110 의료진 확인, 10/30 수인)
HEART = "IHD"
HEART_WALK = {"title": "걷기", "goal_type": "check", "target_value": None, "unit": None}
HEART_APPROVAL = r"승인"


def _disease(did: str) -> dict[str, Any]:
    return next(d for d in lifestyle.facts()["diseases"] if d["id"] == did)


def _pick(text: str, pattern: str | None) -> str:
    """팩트표 글에서 쉼표나 마침표로 나눈 조각 중 pattern이 든 것 (글은 고치지 않음)"""
    if not pattern:
        return text
    parts = [p.strip() for p in re.split(r"[,.]\s*", text) if p.strip()]
    return next((p for p in parts if re.search(pattern, p)), text)


def _backing(s: Source, ids: set[str], drug_names: list[str]) -> str | None:
    """근거가 맞으면 설명 글, 아니면 None"""
    if s.disease not in ids:
        return None
    d = _disease(s.disease)
    if s.category:
        ls = next(x for x in d["lifestyle"] if x["category"] == s.category)
        if s.desc and not re.search(s.desc, ls["goal"]):
            return next((a for a in ls["actions"] if re.search(s.desc, a)), ls["goal"])
        return _pick(ls["goal"], s.desc)
    link = next(m for m in d.get("medication_link", []) if s.drug and s.drug in m["drug_class"])
    words = lifestyle.ingredient_words(link["drug_class"])
    if not any(w in name for name in drug_names for w in words):
        return None
    return _pick(link["advice"], s.desc)


def _heart_desc(goal: str) -> str:
    """팩트표 글 두 개를 고치지 않고 이어 붙임"""
    ls = next(x for x in _disease(HEART)["lifestyle"] if x["category"] == "심장재활 운동")
    approval = next((a for a in ls["actions"] if re.search(HEART_APPROVAL, a)), None)
    return f"{goal}. {approval}" if approval else goal


def recommend(codes: list[str], drug_names: list[str], drinking: str | None) -> list[dict[str, Any]]:
    """codes: 분석의 질병분류기호. drug_names: 분석에 쓴 약 이름. drinking: 내 정보 음주 (없으면 None)"""
    ids = {d["id"] for c in codes if (d := lifestyle.disease_of(c))}
    out: list[dict[str, Any]] = []
    for c in CHALLENGES:
        if drinking in c.skip_drinking:
            continue
        hits = [(s, desc) for s in c.sources if (desc := _backing(s, ids, drug_names))]
        if not hits:
            continue
        reasons = [DRUG_REASON if s.drug else _disease(s.disease)["name"] for s, _ in hits]
        heart = next((_heart_desc(desc) for s, desc in hits if s.disease == HEART), None)
        out.append(
            {
                "key": c.key,
                "title": c.title,
                "desc": heart or hits[0][1],
                "goal_type": c.goal_type,
                "target_value": c.target_value,
                "unit": c.unit,
                "caution_label": HEART_LABEL if heart else None,
                "reason_label": ", ".join(dict.fromkeys(reasons)),
                "fact_refs": [f"{s.disease}:{s.category or s.drug}" for s, _ in hits],
                **(HEART_WALK if heart else {}),
            }
        )
    return out
