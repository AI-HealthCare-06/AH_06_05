"""공공데이터 마스터 넣기 — 심평원 약제급여목록 (drug_products) · 상병마스터 (diseases)

원본 파일은 data/raw/hira/ 에만 둠 (깃허브에 안 올림). 실행은 scripts/data/load_masters.py
"""

import csv
import re
from collections.abc import Iterable
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from app.services.drug_names import normalize_name

# 약제급여목록 칸 순서 (2026.9.1. 공개용): 연번 · 투여 · 분류 · 식약분류 · 주성분코드_동일제형 · 주성분코드 · 주성분개수 ·
# 주성분명 · 제품코드 · 제품명 · 업체명 · 규격 · 단위 · 상한금액 · 전일 · 비고
DRUG_HEADER = (
    "연번",
    "투여",
    "분류",
    "식약분류",
    "주성분코드\n_동일제형",
    "주성분코드",
    "주성분\n개수",
    "주성분명",
    "제품코드",
    "제품명",
    "업체명",
    "규격",
    "단위",
    "상한금액표 금액",
    "전일",
    "비고",
)


def _s(v: Any) -> str:
    return "" if v is None else str(v).strip()


def parse_spec(v: Any) -> Decimal | None:
    """규격 "95(1)" · "1" · "0.5" → 앞의 숫자만 (못 읽으면 None)"""
    m = re.match(r"\d+(?:\.\d+)?", _s(v))
    if not m:
        return None
    try:
        return Decimal(m.group(0))
    except InvalidOperation:
        return None


def parse_drug_row(r: tuple) -> dict | None:
    edi = _s(r[8])
    if not edi:
        return None
    price = r[13]
    return {
        "edi_code": edi.zfill(9),
        "item_name": _s(r[9]),
        "item_name_norm": normalize_name(_s(r[9])),
        "entp_name": _s(r[10]) or None,
        "ingr_code": _s(r[5]) or None,
        "ingr_group": _s(r[4]) or None,
        "etc_otc": _s(r[14]) or None,
        "class_code": _s(r[2]) or None,
        "spec_value": parse_spec(r[11]),
        "spec_unit": _s(r[12]) or None,
        "price": int(price) if isinstance(price, int | float) else None,
        "route": _s(r[1]) or None,
    }


def read_drug_list(path: Path) -> list[dict]:
    import openpyxl  # type: ignore[import-untyped]  # 로컬에서 넣을 때만 필요: uv run --with openpyxl ...

    ws = openpyxl.load_workbook(path, read_only=True).worksheets[0]
    rows = ws.iter_rows(values_only=True)
    header = tuple(_s(h) for h in next(rows))
    if header[:10] != tuple(_s(h) for h in DRUG_HEADER[:10]):
        raise SystemExit(f"약제급여목록 칸 순서가 달라요: {header[:10]}")
    return [d for r in rows if (d := parse_drug_row(r))]


def _int_or_none(v: str) -> int | None:
    return int(v) if v.strip().isdigit() else None


def parse_disease_rows(rows: Iterable[dict]) -> list[dict]:
    """상병마스터는 같은 상병기호에 이름이 여러 줄 (동의어) → 첫 줄(공식 이름)만 씀"""
    out: dict[str, dict] = {}
    for r in rows:
        code = r["상병기호"].strip()
        if not code or code in out:
            continue
        out[code] = {
            "code": code,
            "name_kr": r["한글명"].strip(),
            "name_en": r["영문명"].strip() or None,
            "is_complete": r["완전코드구분"].strip() != "N",
            "main_usable": r["주상병사용구분"].strip() != "N",
            "sex_limit": r["성별구분"].strip() or None,
            "age_min": _int_or_none(r["하한연령"]),
            "age_max": _int_or_none(r["상한연령"]),
        }
    return list(out.values())


def read_diseases(path: Path) -> list[dict]:
    text = path.read_bytes().decode("cp949")
    return parse_disease_rows(csv.DictReader(text.splitlines()))


async def upsert(model, rows: list[dict], key: str, chunk: int = 1000) -> int:
    """같은 키가 있으면 고쳐 쓰고 없으면 넣음 — 여러 번 돌려도 같은 결과 (처방전이 참조해도 안전)"""
    fields = [k for k in rows[0] if k != key] if rows else []
    for i in range(0, len(rows), chunk):
        await model.bulk_create([model(**r) for r in rows[i : i + chunk]], on_conflict=[key], update_fields=fields)
    return len(rows)
