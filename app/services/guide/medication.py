# mypy: disable-error-code=union-attr
"""복약 안내 (RG-04) — AI 없이: 약효분류로 종류 · 쓰임, 처방 숫자로 먹는 법. 주의할 점은 허가정보를 넣기 전까지 null

null이면 화면이 "허가정보에 내용이 없어요"로 보여 줌 (API 명세서 R-4 medication.items)
"""

from decimal import Decimal
from typing import Any

from app.models.masters import DrugProduct
from app.models.ocr import PrescriptionItem
from app.services.drug_names import base_name

# 약효분류(심평원 분류 3자리) → 종류 · 쓰임. 흔한 분류만 — 없으면 종류 null, 쓰임은 약사 확인 문구
# 한 분류 안에 쓰임이 다른 약이 섞인 분류는 넣지 않는다 (219 기타 순환계용약 · 339 기타 혈액용약 · 117 정신신경용제 ·
# 243 갑상선 · 부갑상선 호르몬제 · 245 부신 호르몬제). 예: 243에는 갑상선 호르몬을 줄이는 약도 있어 "보충"이라고 하면 틀림
CLASS_NAME = {
    "214": "혈압약", "213": "이뇨제", "396": "당뇨약", "218": "콜레스테롤약",
    "114": "진통제", "614": "항생제", "618": "항생제", "619": "항생제", "232": "위장약", "222": "호흡기약",
    "333": "항응고제", "394": "통풍약", "113": "항경련제", "122": "근육이완제", "124": "진경제",
    "149": "알레르기약", "237": "정장제", "234": "제산제", "235": "구토 억제제",
}  # fmt: skip
CLASS_PURPOSE = {
    "214": "혈압을 낮춰요", "213": "몸의 물을 빼서 붓기와 혈압을 조절해요", "396": "혈당을 낮춰요", "218": "콜레스테롤을 낮춰요",
    "114": "통증과 열을 줄여요", "232": "위를 보호해요", "614": "세균 감염을 치료해요", "618": "세균 감염을 치료해요",
    "222": "기침 · 가래 · 숨 가쁨 같은 호흡기 증상을 줄여요", "141": "콧물 · 알레르기를 줄여요", "211": "심장을 도와요",
    "619": "세균 감염을 치료해요", "333": "피가 굳는 것을 막아요", "394": "통풍(요산)을 조절해요",
    "113": "경련 · 발작 등 신경 증상을 조절해요", "122": "뭉친 근육의 긴장을 풀어요", "124": "배 · 장의 경련을 줄여요",
    "149": "알레르기 증상을 줄여요", "237": "장 기능을 도와요", "234": "위산을 중화해요",
    "235": "메스꺼움 · 구토를 줄여요",
}  # fmt: skip
PURPOSE_FALLBACK = "처방받은 목적을 약사에게 확인해 주세요"
DOSE_UNITS = {"정", "캡슐", "포", "환"}
SOURCE = "심평원 약제급여목록 약효분류"


def category_of(drug: DrugProduct | None) -> str | None:
    return CLASS_NAME.get((drug.class_code or "")[:3]) if drug else None


def how_to_take(item: PrescriptionItem, drug: DrugProduct) -> str | None:
    def num(v: Decimal) -> str:
        return f"{v:f}".rstrip("0").rstrip(".") if v % 1 else str(int(v))

    parts = []
    if item.times_per_day:
        parts.append(f"하루 {item.times_per_day}번")
    if item.timing:
        parts.append(item.timing)
    if item.dose_per_time:
        parts.append(f"1회 {num(item.dose_per_time)}{drug.spec_unit if drug.spec_unit in DOSE_UNITS else ''}")
    if item.total_days:
        parts.append(f"{item.total_days}일")
    return " · ".join(parts) or None


def static_part(d: DrugProduct) -> dict[str, Any]:
    """약마다 정해지는 부분 (처방과 상관없음) — 배치로 drug_guides에 미리 저장하는 내용"""
    cls = (d.class_code or "")[:3]
    return {
        "category": CLASS_NAME.get(cls),
        "purpose": CLASS_PURPOSE.get(cls, PURPOSE_FALLBACK),
        "caution": None,
        "source": SOURCE,
    }


def evidence_of(d: DrugProduct) -> list[dict[str, str]]:
    """안내문의 근거 목록 — 챗봇이 답에 출처를 붙일 때 그대로 쓴다. 지금은 약효분류 표만, 허가정보를 적재하면 kind="drug_details"(품목기준코드 · 항목)를 더한다"""
    cls = (d.class_code or "")[:3]
    return [{"kind": "hira_class", "key": cls, "label": SOURCE}] if cls in CLASS_PURPOSE else []


def build(items: list[PrescriptionItem], stored: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    """items: drug가 미리 불러와진 점검 대상 약 (확정된 것만)
    stored: drug_guides에서 조회한 '사람이 확인한' 안내문 {edi_code: content}.
    없는 약은 표로 바로 채우지 않고 '약사에게 확인' 문구를 낸다 (사람 확인 전 내용은 보여 주지 않음)"""
    out = []
    for it in items:
        d = it.drug  # type: ignore[assignment]
        base = (stored or {}).get(d.edi_code) or {}
        out.append(
            {
                "itemId": it.id,
                "ediCode": d.edi_code,
                "itemName": base_name(d.item_name),
                "category": base.get("category"),
                "purpose": base.get("purpose") or PURPOSE_FALLBACK,
                "howToTake": how_to_take(it, d),  # type: ignore[arg-type]
                "caution": base.get("caution"),
                "cautions": base.get("cautions") or [],  # 문장별 목록 (caution은 이어 붙인 문자열) — 명세서 추가 제안
                "source": base.get("source"),  # 확인 전 약은 출처 없음 (문구가 표에서 나온 게 아님)
            }
        )
    return {"items": out}
