"""약 이름 정규화 — 약제급여목록 이름과 OCR이 읽은 이름을 같은 모양으로 맞춤 (맛보기 #29)

예: "노바스크정5밀리그람(암로디핀베실산염)_(6.944mg/1정)" → "노바스크정5밀리그램(암로디핀베실산염)"
"""

import re


def base_name(name: str) -> str:
    """규격 "_(6.944mg/1정)"을 떼고 공백을 없앰"""
    return re.sub(r"\s", "", name.split("_(")[0])


def unify(name: str) -> str:
    """표기 통일: 밀리그람 · mg → 밀리그램 (통일 없이 하면 비슷한 다른 약을 1등으로 고름)"""
    return name.lower().replace("밀리그람", "밀리그램").replace("mg", "밀리그램")


def normalize_name(name: str) -> str:
    return unify(base_name(name))
