# mypy: ignore-errors
# ruff: noqa
# 시험 폴더(rag_sandbox/safety)에서 검증한 코드를 거의 그대로 옮긴 파일이라 린트 · 포맷 규칙을 적용하지 않음 (고친 곳은 "서버 변경"으로 표시)
"""안전성 점검 (피처 2 RAG ②단계) — DB 조회로만 판정, AI 안 씀 (NFR-032)

사용:
    from safety_check import SafetyChecker, Item, Patient
    checker = SafetyChecker("safety.sqlite")
    result = checker.check(items, Patient(birth_year=1958, sex="F"), today=date(2026, 10, 2))

정한 기준 (10/2 팀 의견)
1. 같은 성분 · 효능군 · 병용금기는 먹는 기간을 봄 (처방일 + 처방 일수)
   - 기간이 겹침 → 원래 등급 (병용금기 위험, 중복 주의)
   - 겹치지 않지만 앞 약이 끝난 지 30일 이내 → 한 단계 낮춰 "남은 약을 아직 드시고 있다면" 문구
     (병용금기 → 주의, 중복 → 참고)
   - 30일 넘게 지남 → 경고 안 띄움
   - 같은 처방전 안의 약 · 날짜를 모르는 약은 함께 먹는 것으로 봄
2. 먹는 약(약제급여목록 "내복")만 점검. 외용 · 주사 · 기타는 "점검 대상이 아니에요"
3. 출생연도만 알아서 나이가 두 가지일 수 있음 → 둘 중 하나라도 기준에 걸리면 경고
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import date, timedelta
from itertools import combinations

RECENT_DAYS = 30  # 끝난 지 이 날수 이내면 "남은 약" 문구
POLYPHARMACY_MIN = 5  # REQ-049 (10/2 회의: 5개)
SEVERITY_ORDER = {"danger": 0, "caution": 1, "info": 2}
DOWNGRADE = {"danger": "caution", "caution": "info", "info": "info"}
OPS = {
    "<": lambda v, x: v < x,
    "<=": lambda v, x: v <= x,
    ">": lambda v, x: v > x,
    ">=": lambda v, x: v >= x,
}


@dataclass
class Item:
    """처방전의 약 한 줄 (OCR → 사용자 확인이 끝난 것)"""

    item_id: str
    edi_code: str
    prescription_id: str
    issued_date: date | None = None  # 처방 교부일
    total_days: int | None = None  # 처방 일수
    dose_per_time: float | None = None  # 1회 투약량 (정 · 캡슐 · mL 등 제품 단위)
    times_per_day: int | None = None  # 1일 투여 횟수
    hospital: str | None = None

    def period(self) -> tuple[date, date] | None:
        if self.issued_date is None or not self.total_days:
            return None
        return self.issued_date, self.issued_date + timedelta(days=self.total_days - 1)


@dataclass
class Patient:
    birth_year: int
    sex: str | None = None  # "M" / "F"


@dataclass
class Warning:
    warning_type: (
        str  # interaction / duplicate_ingredient / duplicate_efficacy / elderly / age / dose_exceed / polypharmacy
    )
    severity: str  # danger / caution / info
    item_ids: tuple[str, ...]
    summary: str  # 화면 문장 (템플릿)
    reason: str | None = None  # DUR 사유 원문
    source: str | None = None
    notice_date: str | None = None
    detail: dict = field(default_factory=dict)


@dataclass
class CheckResult:
    warnings: list[Warning]
    checked: list[str]  # 점검한 item_id
    not_checked: list[dict]  # [{item_id, reason}] — 화면에 "점검 대상이 아니에요"
    checked_types: list[str]  # 점검한 항목 (RG-02-E1 "점검한 항목")


class SafetyChecker:
    def __init__(self, db_path: str):
        self.db = sqlite3.connect(
            f"file:{db_path}?mode=ro&immutable=1", uri=True, check_same_thread=False
        )  # 서버 변경: 요청마다 다른 스레드에서 읽으므로 (읽기 전용이라 안전)
        self.db.row_factory = sqlite3.Row

    # ---------- 공통 ----------
    def _q(self, sql: str, *args):
        return self.db.execute(sql, args).fetchall()

    @staticmethod
    def _ymd(d: date) -> str:
        return d.strftime("%Y%m%d")

    @staticmethod
    def _fmt_notice(v: str | None) -> str | None:
        return f"{v[:4]}-{v[4:6]}-{v[6:8]}" if v and len(v) == 8 else None

    @staticmethod
    def age_range(birth_year: int, today: date, unit: str) -> tuple[float, float]:
        """출생연도만 알 때 가능한 나이 범위 (가장 늦게 태어난 날 ~ 가장 일찍 태어난 날)"""
        latest, earliest = date(birth_year, 12, 31), date(birth_year, 1, 1)

        def age_in(born: date) -> float:
            if unit == "세":
                return today.year - born.year - ((today.month, today.day) < (born.month, born.day))
            if unit == "개월":
                months = (today.year - born.year) * 12 + today.month - born.month
                return months - (today.day < born.day)
            if unit == "주":
                return (today - born).days // 7
            raise ValueError(unit)

        return age_in(latest), age_in(earliest)

    def _age_may_match(self, patient: Patient, today: date, age: int, unit: str, op: str) -> bool:
        lo, hi = self.age_range(patient.birth_year, today, unit)
        # 조건은 나이가 커지거나 작아질 때 한쪽으로만 바뀜 → 양 끝만 보면 됨
        return OPS[op](lo, age) or OPS[op](hi, age)

    @staticmethod
    def timing(a: Item, b: Item) -> tuple[str, int | None]:
        """두 약을 함께 먹는지: overlap(겹침) / recent(끝난 지 30일 이내) / none"""
        if a.prescription_id == b.prescription_id:
            return "overlap", None
        pa, pb = a.period(), b.period()
        if pa is None or pb is None:
            return "overlap", None  # 날짜를 모르면 함께 먹는 것으로 봄 (놓치지 않게)
        if pa[0] <= pb[1] and pb[0] <= pa[1]:
            return "overlap", None
        first, second = (pa, pb) if pa[1] < pb[0] else (pb, pa)
        gap = (second[0] - first[1]).days - 1  # 끝난 다음 날부터 새 약 시작 전날까지
        return ("recent", gap) if gap <= RECENT_DAYS else ("none", gap)

    # ---------- 점검 ----------
    def check(self, items: list[Item], patient: Patient, today: date | None = None) -> CheckResult:
        today = today or date.today()
        t = self._ymd(today)
        products = (
            {
                r["edi_code"]: r
                for r in self._q(
                    f"SELECT * FROM drug_products WHERE edi_code IN ({','.join('?' * len(items))})",
                    *[i.edi_code for i in items],
                )
            }
            if items
            else {}
        )

        oral, not_checked = [], []
        for it in items:
            p = products.get(it.edi_code)
            if p is None:
                not_checked.append({"item_id": it.item_id, "reason": "unknown_drug"})
            elif p["route"] != "내복":
                not_checked.append({"item_id": it.item_id, "reason": "not_oral", "route": p["route"]})
            else:
                oral.append(it)

        name = {it.item_id: products[it.edi_code]["product_name"] for it in oral}
        warnings: list[Warning] = []
        warnings += self._interactions(oral, products, patient, today, t, name)
        dup_pairs, dup_warnings = self._duplicate_ingredient(oral, products, name)
        warnings += dup_warnings
        warnings += self._duplicate_efficacy(oral, dup_pairs, name)
        warnings += self._elderly(oral, products, patient, today, t)
        warnings += self._age_limit(oral, products, patient, today, t)
        warnings += self._dose(oral, products, patient, today, t)
        warnings += self._polypharmacy(oral)

        warnings.sort(key=lambda w: (SEVERITY_ORDER[w.severity], w.warning_type, w.item_ids))
        return CheckResult(
            warnings=warnings,
            checked=[i.item_id for i in oral],
            not_checked=not_checked,
            checked_types=[
                "interaction",
                "duplicate_ingredient",
                "duplicate_efficacy",
                "elderly",
                "age",
                "dose_exceed",
                "polypharmacy",
            ],
        )

    def _pair_label(self, a: Item, b: Item, name: dict) -> dict:
        return {
            "drugs": [
                {
                    "item_id": x.item_id,
                    "name": name[x.item_id],
                    "hospital": x.hospital,
                    "until": (x.period()[1].isoformat() if x.period() else None),
                }
                for x in (a, b)
            ]
        }

    # 1) 병용금기 (점검 프로그램 00번 규칙 + 기간)
    def _interactions(self, oral, products, patient, today, t, name):
        out = []
        for a, b in combinations(oral, 2):
            ca, cb = products[a.edi_code]["ingr_code"], products[b.edi_code]["ingr_code"]
            when, gap = self.timing(a, b)
            if when == "none":
                continue
            rows = self._q(
                "SELECT * FROM dur_interaction WHERE ((code_a=? AND code_b=?) OR (code_a=? AND code_b=?))"
                " AND ? BETWEEN valid_from AND valid_to",
                ca,
                cb,
                cb,
                ca,
                t,
            )
            hit = None
            for r in rows:
                if r["sex"] in ("M", "F") and patient.sex != r["sex"]:
                    continue
                if r["spc_age"] and not self._age_may_match(patient, today, r["spc_age"], "세", r["spc_age_cond"]):
                    continue
                excepted = self._q(
                    "SELECT 1 FROM dur_interaction_exception WHERE code_a=? AND code_b=? AND edi_code IN (?,?)"
                    " AND ? BETWEEN valid_from AND valid_to",
                    r["code_a"],
                    r["code_b"],
                    a.edi_code,
                    b.edi_code,
                    t,
                )
                if excepted:
                    continue
                hit = r
                break
            if hit is None:
                continue
            severity, summary = "danger", "함께 드시면 안 되는 약이에요"
            if when == "recent":
                severity = DOWNGRADE[severity]
                summary = (
                    "최근까지 드신 약과 함께 드시면 안 되는 약이에요. 남은 약을 아직 드시고 있다면 함께 드시지 마세요"
                )
            out.append(
                Warning(
                    "interaction",
                    severity,
                    (a.item_id, b.item_id),
                    summary,
                    reason=hit["reason"],
                    source="심평원 DUR 병용금기",
                    notice_date=self._fmt_notice(hit["notice_date"]),
                    detail={**self._pair_label(a, b, name), "timing": when, "gap_days": gap},
                )
            )
        return out

    # 2) 동일성분 (DUR성분코드, 복합제는 여러 개)
    def _ingredients(self, it: Item, products) -> set[str]:
        codes = {
            r["dur_ingr_code"]
            for r in self._q("SELECT dur_ingr_code FROM dup_ingredient WHERE edi_code=?", it.edi_code)
        }
        if not codes and products[it.edi_code]["ingr_count"] == 1:
            codes = {"PREFIX:" + products[it.edi_code]["ingr_code"][:4]}  # 목록에 없는 단일 성분 약: 성분 앞 4자리
        return codes

    def _duplicate_ingredient(self, oral, products, name):
        out, pairs = [], set()
        ingr = {it.item_id: self._ingredients(it, products) for it in oral}
        names = {
            r["dur_ingr_code"]: r["dur_ingr_name"]
            for r in self._q("SELECT dur_ingr_code, dur_ingr_name FROM dup_ingredient")
        }
        for a, b in combinations(oral, 2):
            common = ingr[a.item_id] & ingr[b.item_id]
            if not common:
                continue
            pairs.add((a.item_id, b.item_id))
            when, gap = self.timing(a, b)
            if when == "none":
                continue
            severity, summary = "caution", "같은 성분 약을 함께 드시고 있어요"
            if when == "recent":
                severity = DOWNGRADE[severity]
                summary = "최근까지 드신 약과 성분이 같아요. 남은 약을 아직 드시고 있다면 함께 드시지 마세요"
            out.append(
                Warning(
                    "duplicate_ingredient",
                    severity,
                    (a.item_id, b.item_id),
                    summary,
                    source="심평원 DUR 동일성분 중복점검 품목리스트",
                    detail={
                        **self._pair_label(a, b, name),
                        "timing": when,
                        "gap_days": gap,
                        "ingredients": sorted(names.get(c, c) for c in common),
                    },
                )
            )
        return pairs, out

    # 3) 효능군 중복 — 점검코드 앞 4자리(약리 계열)가 같고 성분(코드)이 다른 두 약
    #    예: 114A = 비스테로이드 소염진통제 (114A0019 이부프로펜 + 114A0032 나프록센 → 중복)
    #        114B = 아세트아미노펜 계열 → 이부프로펜(114A)과는 중복 아님
    #    같은 성분끼리는 2) 동일성분에서 이미 봄
    def _duplicate_efficacy(self, oral, dup_pairs, name):
        out = []
        codes = {}
        for it in oral:
            codes[it.item_id] = {
                (r["check_code"], r["group_name"])
                for r in self._q("SELECT check_code, group_name FROM dup_efficacy WHERE edi_code=?", it.edi_code)
            }
        for a, b in combinations(oral, 2):
            if (a.item_id, b.item_id) in dup_pairs:
                continue
            common = {
                (ca[:4], ga)
                for ca, ga in codes[a.item_id]
                for cb, _ in codes[b.item_id]
                if ca[:4] == cb[:4] and ca != cb
            }
            if not common:
                continue
            when, gap = self.timing(a, b)
            if when == "none":
                continue
            severity, summary = "caution", "효과가 비슷한 약을 함께 드시고 있어요"
            if when == "recent":
                severity = DOWNGRADE[severity]
                summary = "최근까지 드신 약과 효과가 비슷한 약이에요. 남은 약을 아직 드시고 있다면 함께 드시지 마세요"
            out.append(
                Warning(
                    "duplicate_efficacy",
                    severity,
                    (a.item_id, b.item_id),
                    summary,
                    source="심평원 DUR 효능군중복 품목리스트",
                    detail={
                        **self._pair_label(a, b, name),
                        "timing": when,
                        "gap_days": gap,
                        "groups": sorted({g for _, g in common}),
                        "classes": sorted({c for c, _ in common}),
                    },
                )
            )
        return out

    # 4) 노인주의 (점검 프로그램 25번)
    def _elderly(self, oral, products, patient, today, t):
        out = []
        for it in oral:
            r = self._q(
                "SELECT * FROM dur_elderly WHERE ingr_code=? AND ? BETWEEN valid_from AND valid_to",
                products[it.edi_code]["ingr_code"],
                t,
            )
            if r and self._age_may_match(patient, today, r[0]["age"], "세", ">="):
                out.append(
                    Warning(
                        "elderly",
                        "caution",
                        (it.item_id,),
                        f"{r[0]['age']}세 이상 어르신은 주의해서 드셔야 하는 약이에요",
                        reason=r[0]["reason"],
                        source="심평원 DUR 노인주의",
                    )
                )
        return out

    # 5) 연령금기 (점검 프로그램 01번: 단위 · 조건 · 예외 제품)
    def _age_limit(self, oral, products, patient, today, t):
        out = []
        for it in oral:
            code = products[it.edi_code]["ingr_code"]
            if self._q("SELECT 1 FROM dur_age_limit_exception WHERE ingr_code=? AND edi_code=?", code, it.edi_code):
                continue
            for r in self._q(
                "SELECT * FROM dur_age_limit WHERE ingr_code=? AND ? BETWEEN valid_from AND valid_to", code, t
            ):
                if self._age_may_match(patient, today, r["age"], r["unit"], r["op"]):
                    out.append(
                        Warning(
                            "age",
                            "danger",
                            (it.item_id,),
                            f"{r['age']}{r['cond_text']}에게는 쓰지 않는 약이에요",
                            reason=r["reason"],
                            source="심평원 DUR 연령금기",
                            notice_date=self._fmt_notice(r["notice_date"]),
                            detail={"age": r["age"], "unit": r["unit"], "op": r["op"]},
                        )
                    )
                    break
        return out

    # 6) 1일 최대용량 (점검 프로그램 03번: 같은 성분군 합산)
    def _dose(self, oral, products, patient, today, t):
        out, by_group = [], {}
        for it in oral:
            rows = self._q(
                "SELECT * FROM dur_dose_limit WHERE ingr_code=? AND ? BETWEEN valid_from AND valid_to",
                products[it.edi_code]["ingr_code"],
                t,
            )
            rows = [
                r
                for r in rows
                if (r["sex"] in (None, "", patient.sex))
                and (not r["age"] or self._age_may_match(patient, today, r["age"], r["age_unit"] or "세", r["age_op"]))
            ]
            if not rows:
                continue
            limit = min(rows, key=lambda r: r["daily_max"])  # 여러 줄이면 가장 엄격한 기준
            by_group.setdefault(limit["group_code"], []).append((it, limit))
        for group, members in by_group.items():
            usable = [(it, r) for it, r in members if it.dose_per_time and it.times_per_day]
            if not usable:
                continue
            days = sorted({it.issued_date for it, _ in usable if it.issued_date} or {today})
            daily_max = min(r["daily_max"] for _, r in usable)
            worst, worst_items = 0.0, ()
            for d in days:
                active = [(it, r) for it, r in usable if it.period() is None or it.period()[0] <= d <= it.period()[1]]
                total = sum(it.dose_per_time * it.times_per_day * r["unit_amount"] for it, r in active)
                if total > worst:
                    worst, worst_items = total, tuple(it.item_id for it, _ in active)
            if worst > daily_max:
                r0 = usable[0][1]
                out.append(
                    Warning(
                        "dose_exceed",
                        "caution",
                        worst_items,
                        "하루에 드시는 양이 정해진 최대량보다 많아요",
                        reason=r0["daily_max_text"],
                        source="심평원 DUR 용량주의",
                        detail={"ingredient": r0["ingr_name"], "daily_total": round(worst, 3), "daily_max": daily_max},
                    )
                )
        return out

    # 7) 다제약물 (REQ-049: 지금 함께 먹는 약 5개 이상)
    def _polypharmacy(self, oral):
        if not oral:
            return []
        dated = [i.issued_date for i in oral if i.issued_date]
        ref = max(dated) if dated else None
        current = [i for i in oral if ref is None or i.period() is None or i.period()[0] <= ref <= i.period()[1]]
        kinds = {i.edi_code for i in current}
        if len(kinds) >= POLYPHARMACY_MIN:
            return [
                Warning(
                    "polypharmacy",
                    "info",
                    tuple(i.item_id for i in current),
                    f"약을 {len(kinds)}가지 함께 드시고 있어요. 약사와 한 번 상의해 보세요",
                    source="요구사항 REQ-049 (5개 이상)",
                    detail={"count": len(kinds)},
                )
            ]
        return []
