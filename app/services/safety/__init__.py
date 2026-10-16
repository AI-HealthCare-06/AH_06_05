"""안전성 점검 (피처 2 ②단계) — 심평원 DUR 조회로만 판정, AI 안 씀 (NFR-032)

checker.py = 점검 본체(시험 폴더 safety_check.py), robust.py = 출생연도 모름 · 이상값 보강, combo.py = 복합제 구성 성분 확장(기본 꺼짐)
"""

import re
import threading
from pathlib import Path

from app.core import config
from app.services.safety.checker import SafetyChecker
from app.services.safety.combo import ComboAwareChecker
from app.services.safety.robust import RobustChecker


class ServerChecker(RobustChecker, ComboAwareChecker):
    """보강판 + 복합제 확장"""


_checker: SafetyChecker | None = None
_lock = threading.Lock()  # 한 연결을 여러 요청이 같이 쓰지 않게 점검은 한 번에 하나씩


class SafetyDbMissingError(RuntimeError):
    """SAFETY_DB_PATH가 없거나 파일이 없음 → 분석의 안전성 단계가 SAFETY_CHECK_FAILED로 끝남"""


def get_checker() -> SafetyChecker:
    global _checker
    if _checker is None:
        path = Path(config.SAFETY_DB_PATH) if config.SAFETY_DB_PATH else None
        if path is None or not path.is_file():
            raise SafetyDbMissingError("안전성 점검 DB(SAFETY_DB_PATH)를 찾을 수 없어요")
        _checker = (ServerChecker if config.SAFETY_COMBO_EXT else RobustChecker)(str(path))
    return _checker


def reset_checker() -> None:
    global _checker
    _checker = None


def check_lock() -> threading.Lock:
    return _lock


def ingredient_names(edi_codes: list[str]) -> dict[str, str | None]:
    """제품코드 → 성분명 (R-5 경고 자세히). 점검 DB가 없으면 빈 값"""
    if not edi_codes:
        return {}
    with _lock:
        rows = get_checker()._q(
            f"SELECT edi_code, ingr_name FROM drug_products WHERE edi_code IN ({','.join('?' * len(edi_codes))})",
            *edi_codes,
        )
    return {r["edi_code"]: re.split(r"\s{2,}", r["ingr_name"] or "")[0] or None for r in rows}  # "성분  0.1g" → 성분
