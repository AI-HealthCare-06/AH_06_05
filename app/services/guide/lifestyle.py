# mypy: disable-error-code=union-attr
"""생활습관 안내 (RG-05) — 팩트 테이블(data/lifestyle_facts.json)을 그대로 보여 줌, AI 안 씀

- 처방전 질병분류기호(KCD) 앞 3자리가 팩트 테이블의 질환 코드 목록에 있으면 그 질환의 안내를 냄
- 약과 함께 조심할 것: 팩트 테이블의 약 종류 설명에서 성분명을 뽑아 처방 약 이름에 있으면 연결
- 질환 둘 이상이 겹칠 때의 주의 문구 4개는 사람이 쓴 초안 (채연 승인 전)
※ 팩트 테이블은 v0.2 초안이라 수치는 의료 담당자 검수가 필요함
"""

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.models.ocr import PrescriptionItem
from app.services.drug_names import display_name

FACTS = Path(__file__).resolve().parent / "data" / "lifestyle_facts.json"
CONFLICT_LABEL = "의료진 상담 필요"
# 질환 선택 화면(RG-05-E1)에서 고를 수 있는 질환 = 팩트 테이블 질환 10개 (대표 코드)
PICKABLE = {"HTN": "I10", "DM2": "E11", "DLP": "E78", "CKD": "N18", "IHD": "I25", "STROKE": "I63", "AF": "I48", "COPD": "J44", "OP": "M81", "OA": "M17"}  # fmt: skip
# 약 종류 설명에서 성분명이 아닌 말 (이 말이 들어간 약 이름과 엉뚱하게 이어지지 않게)
GENERIC_WORDS = {"소염진통제", "조영제", "사용", "검사", "건강보조식품", "흡입기", "경구", "스테로이드", "주사", "제외", "질환으로", "장기", "복용", "보전", "이뇨제", "억제제", "차단제", "보충제", "항응고제", "항혈소판제", "비스포스포네이트"}  # fmt: skip

# 질환이 겹칠 때의 안내 (초안). 조건은 팩트 테이블 질환 id 기준
CONFLICTS: list[dict[str, Any]] = [
    {
        "anchor": "HTN",
        "when": lambda ids, codes: {"HTN", "CKD"} <= ids,
        "message": "고혈압과 만성신장병이 함께 있으면 칼륨 섭취 권고가 서로 달라요. 칼륨이 많은 음식이나 보충제는 임의로 늘리거나 줄이지 말고 의료진과 상담하세요.",
    },
    {
        "anchor": "DM2",
        "when": lambda ids, codes: {"DM2", "CKD"} <= ids,
        "message": "당뇨병과 만성신장병이 함께 있으면 단백질 섭취 기준이 신장 상태에 따라 달라요. 일반적인 안내 대신 의료진과 상담하세요.",
    },
    {
        "anchor": "OA",
        "when": lambda ids, codes: "OA" in ids and ("CKD" in ids or any(c.startswith(("I50", "K25")) for c in codes)),
        "message": "골관절염과 함께 신장 · 심장 · 위 질환이 있으면 소염진통제(NSAIDs)를 특히 조심해야 해요. 통증약을 사기 전에 약사나 의료진과 상의하고, 아세트아미노펜을 먼저 쓸 수 있는지 확인하세요.",
    },
    {
        # 약이 5개 이상일 때의 안내는 여기서 하지 않는다: 안전성 점검 결과(R-4)에 "여러 약 함께 복용"(참고)이 이미 있고,
        # 거기서는 먹는 약 · 지금 함께 먹는 약만 세는데 이 안내는 질환과 상관없는 첫 항목에 붙어 세는 기준도 달랐다
        "anchor": "AF",
        "when": lambda ids, codes: {"AF", "OP"} <= ids,
        "message": "여러 약이나 건강기능식품을 함께 드시면 복용 간격과 상호작용을 확인해야 해요. 새 건강기능식품을 추가하기 전에 꼭 상담하세요.",
    },
]


@lru_cache(maxsize=1)
def facts() -> dict[str, Any]:
    return json.loads(FACTS.read_text(encoding="utf-8"))


def disease_of(code: str) -> dict[str, Any] | None:
    """KCD 코드 → 팩트 테이블 질환 (앞 3자리로 찾음). 없으면 None"""
    c = code.strip().upper()[:3]
    return next((d for d in facts()["diseases"] if c in d["kcd"]), None)


def is_supported(code: str) -> bool:
    return disease_of(code) is not None


def _ingredient_words(drug_class: str) -> set[str]:
    """ "칼슘차단제 (암로디핀, 니페디핀 등)" → {"암로디핀", "니페디핀"} / "메트포르민" → {"메트포르민"}"""
    inner = re.findall(r"\(([^)]*)\)", drug_class)
    text = " ".join(inner) if inner else drug_class
    text = text.split("—")[0]
    return {w for w in re.findall(r"[가-힣]{3,}", text) if w not in GENERIC_WORDS and w != "등"}


def build(codes: list[str], items: list[PrescriptionItem], all_codes: list[str] | None = None) -> dict[str, Any]:  # noqa: C901
    """codes: [(질환 코드)] — 출처 구분은 호출한 쪽(분석 질환 행). items: drug가 불러와진 약. all_codes: 겹침 판단용 원래 코드"""
    sources: dict[str, int] = {}

    def source_ids(text: str | None) -> list[int]:
        ids: list[int] = []
        for part in [p.strip() for p in (text or "").split(" / ") if p.strip()]:
            ids.append(sources.setdefault(part, 31 + len(sources)))
        return ids

    found: list[tuple[str, dict[str, Any]]] = []
    seen: set[str] = set()
    for code in codes:
        d = disease_of(code)
        if d and d["id"] not in seen:
            seen.add(d["id"])
            found.append((code, d))

    diseases: list[dict[str, Any]] = []
    sections: list[dict[str, Any]] = []
    signs: list[dict[str, Any]] = []
    links: list[dict[str, Any]] = []
    for code, d in found:
        diseases.append({"code": code, "name": d["name"]})
        for ls in d["lifestyle"]:
            ids = source_ids(ls.get("source"))
            sections.append(
                {
                    "diseaseCode": code,
                    "title": ls["category"],
                    "goal": ls.get("goal"),
                    "actions": [{"text": a, "kind": "fact", "sourceIds": ids} for a in ls.get("actions", [])],
                    "conflict": None,
                }
            )
        if d.get("warning_signs"):
            signs.append(
                {
                    "diseaseCode": code,
                    "actions": [{"text": s, "kind": "fact", "sourceIds": []} for s in d["warning_signs"]],
                }
            )
        for ml in d.get("medication_link", []):
            words = _ingredient_words(ml["drug_class"])
            for it in items:
                if any(w in it.drug.item_name for w in words):
                    clinician = bool(ml.get("requires_clinician"))
                    advice = [s.strip() for s in re.split(r"\.\s*", ml["advice"]) if s.strip()]
                    if any(
                        x["itemId"] == it.id and x["actions"] and x["actions"][0]["text"] == advice[0] for x in links
                    ):
                        continue  # 질환 두 개가 같은 약 종류를 가리켜도 한 번만
                    links.append(
                        {
                            "itemId": it.id,
                            "itemName": display_name(it.drug.item_name),
                            "requiresClinician": clinician,
                            "actions": [{"text": s, "kind": "safety_notice", "sourceIds": []} for s in advice],
                        }
                    )

    disease_ids = {d["id"] for _, d in found}
    did = {code: d["id"] for code, d in found}
    raw = [c.upper() for c in (all_codes or codes)]
    for rule in CONFLICTS:
        if not rule["when"](disease_ids, raw):
            continue
        free = [s for s in sections if not s["conflict"]]
        target = next((s for s in free if did.get(s["diseaseCode"]) == rule["anchor"]), None) or next(iter(free), None)
        if target:
            target["conflict"] = {"message": rule["message"], "label": CONFLICT_LABEL}

    return {
        "diseases": diseases,
        "medicationLinks": links,
        "sections": sections,
        "warningSigns": signs,
        "sources": [
            {"id": i, "org": name, "title": "", "edition": None, "publishedAt": None, "url": None}
            for name, i in sources.items()
        ],
    }
