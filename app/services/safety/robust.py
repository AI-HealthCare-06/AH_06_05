# mypy: ignore-errors
# ruff: noqa
# 시험 폴더(rag_sandbox/safety)에서 검증한 코드를 거의 그대로 옮긴 파일이라 린트 · 포맷 규칙을 적용하지 않음 (고친 곳은 "서버 변경"으로 표시)
"""안전성 점검 보강판 (10/13 시험용, 원본 safety_check.py는 고치지 않음)

문제: 출생연도를 못 읽었거나(None) 말이 안 되는 값(0, 1800, 미래)이면
  - None, 0 은 노인주의 · 연령금기 · 용량 점검에서 예외(TypeError, ValueError)로 멈춘다
  - 미래 출생연도(2030)는 음수 나이로 계산돼 "어린이에게 쓰지 않는 약" 같은 엉뚱한 연령금기를 띄운다
보강: 출생연도가 1900년~올해가 아니면 '모름'으로 보고 나이가 들어가는 점검(노인주의 · 연령금기 · 나이 조건이 붙은 병용금기와 용량)을 건너뛴다.
      건너뛴 항목은 result.skipped_types 에 이유와 함께 담아 화면에서 "출생연도를 알려 주시면 점검해요"라고 안내하게 한다.
      나이와 상관없는 점검(병용금기, 동일성분, 효능군, 다제약물, 나이 조건 없는 용량)은 그대로 돌린다.
"""

from __future__ import annotations

from datetime import date

from app.services.safety.checker import CheckResult, Patient, SafetyChecker

AGE_TYPES = ("elderly", "age")


class RobustChecker(SafetyChecker):
    _age_unknown = False

    def _age_may_match(self, patient, today, age, unit, op):
        if self._age_unknown:
            return False
        return super()._age_may_match(patient, today, age, unit, op)

    def check(self, items, patient: Patient, today: date | None = None) -> CheckResult:
        today = today or date.today()
        by = getattr(patient, "birth_year", None)
        self._age_unknown = not (isinstance(by, int) and 1900 <= by <= today.year)
        try:
            res = super().check(items, patient, today)
        finally:
            unknown = self._age_unknown
            self._age_unknown = False
        res.skipped_types = []
        if unknown:
            res.checked_types = [t for t in res.checked_types if t not in AGE_TYPES]
            res.skipped_types = [{"type": t, "reason": "birth_year_unknown"} for t in AGE_TYPES]
        return res
