# mypy: ignore-errors
# ruff: noqa
# 시험 폴더(rag_sandbox/safety)에서 검증한 코드를 거의 그대로 옮긴 파일이라 린트 · 포맷 규칙을 적용하지 않음 (고친 곳은 "서버 변경"으로 표시)
"""복합제 확장 점검 (10/13 시험용, 원본 safety_check.py는 고치지 않음)

문제: 심평원 병용금기 · 노인주의 · 연령금기 목록은 코드 하나(예: 480600ATB = 아세트아미노펜+트라마돌 복합제)에 대해 적혀 있다.
      복합제 670개 코드 중 100개(15%, 제품 약 478개)는 자기 코드로 등록된 병용금기가 없거나 부족한데,
      들어 있는 성분(예: 트라마돌) 단독으로는 병용금기가 있다. 원본은 자기 코드만 보므로 이런 복합제는 놓친다.
확장: 복합제(성분 2~4개)는 자기 코드에 더해 '구성 성분 단독 코드'도 목록에서 찾는다.
      자기 코드로 걸린 것은 원본과 똑같이 두고, 구성 성분 기준으로만 걸린 것은 detail["basis"]="component"로 표시하고 문구를 달리한다.
      (심평원 원문에 복합제 항목이 없는 경고이므로 화면에서 출처를 구분해 보여 주고, 약사 검토를 받은 뒤 켜는 것을 권한다)
"""

from __future__ import annotations
import re
from itertools import combinations
from app.services.safety.checker import SafetyChecker, Warning, DOWNGRADE

SALTS = {
    "hydrochloride",
    "sodium",
    "calcium",
    "potassium",
    "besylate",
    "sulfate",
    "maleate",
    "tartrate",
    "succinate",
    "bisulfate",
    "mesylate",
    "fumarate",
    "phosphate",
    "acetate",
    "citrate",
    "magnesium",
    "hydrobromide",
    "trihydrate",
    "dihydrate",
    "monohydrate",
    "hemihydrate",
    "disoproxil",
    "bromide",
    "nitrate",
    "lactate",
    "tosylate",
    "napsylate",
    "valerate",
    "propionate",
    "dipropionate",
    "hcl",
    "anhydrous",
    "hydrate",
    "medoxomil",
    "etexilate",
    "cilexetil",
    "axetil",
    "pivoxil",
    "alafenamide",
    "dimesylate",
    "oxalate",
    "gluconate",
    "carbonate",
}


def canon(part: str) -> str:
    p = part.strip().lower()
    m = re.search(r"\(as\s+([^)\d]+?)[\s\d]", p)  # "(as amlodipine 10mg)" 안의 본래 성분명을 우선
    if m:
        p = m.group(1)
    p = re.sub(r"\(.*?\)", " ", p)
    p = re.sub(r"[\d.]+\s*(mg|g|mcg|ug|iu|ml|%|unit|units|miu|/정|/캡슐).*", "", p)
    words = [w for w in re.split(r"[\s,]+", p) if w and w not in SALTS]
    return " ".join(words)


def split_components(ingr_name: str) -> list[str]:
    parts, depth, cur = [], 0, ""
    for ch in ingr_name:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    parts.append(cur)
    return [canon(x) for x in parts if canon(x)]


class ComboAwareChecker(SafetyChecker):
    def __init__(self, db_path: str):
        super().__init__(db_path)
        single: dict[str, set[str]] = {}
        for r in self._q("SELECT ingr_code, ingr_name FROM drug_products WHERE ingr_count=1"):
            cs = split_components(r["ingr_name"])
            if cs:
                single.setdefault(cs[0], set()).add(r["ingr_code"])
        self.components: dict[str, set[str]] = {}
        self.unmapped: dict[str, list[str]] = {}
        for r in self._q(
            "SELECT DISTINCT ingr_code, ingr_name, ingr_count FROM drug_products WHERE ingr_count BETWEEN 2 AND 4"
        ):
            codes, miss = set(), []
            for cn in split_components(r["ingr_name"]):
                s = single.get(cn)
                if s:
                    codes |= s
                else:
                    miss.append(cn)
            self.components[r["ingr_code"]] = codes
            if miss:
                self.unmapped[r["ingr_code"]] = miss

    def _codes(self, products, it):
        own = products[it.edi_code]["ingr_code"]
        return own, self.components.get(own, set()) - {own}

    # ---- 병용금기
    def _interactions(self, oral, products, patient, today, t, name):
        out = super()._interactions(oral, products, patient, today, t, name)
        have = {frozenset(w.item_ids) for w in out}
        for a, b in combinations(oral, 2):
            if frozenset((a.item_id, b.item_id)) in have:
                continue
            oa, ca = self._codes(products, a)
            ob, cb = self._codes(products, b)
            if not ca and not cb:
                continue
            when, gap = self.timing(a, b)
            if when == "none":
                continue
            sa, sb = {oa} | ca, {ob} | cb
            hit = None
            for x in sa:
                for y in sb:
                    if (x, y) == (oa, ob):
                        continue
                    for r in self._q(
                        "SELECT * FROM dur_interaction WHERE ((code_a=? AND code_b=?) OR (code_a=? AND code_b=?))"
                        " AND ? BETWEEN valid_from AND valid_to",
                        x,
                        y,
                        y,
                        x,
                        t,
                    ):
                        if r["sex"] in ("M", "F") and patient.sex != r["sex"]:
                            continue
                        if r["spc_age"] and not self._age_may_match(
                            patient, today, r["spc_age"], "세", r["spc_age_cond"]
                        ):
                            continue
                        if self._q(
                            "SELECT 1 FROM dur_interaction_exception WHERE code_a=? AND code_b=? AND edi_code IN (?,?)"
                            " AND ? BETWEEN valid_from AND valid_to",
                            r["code_a"],
                            r["code_b"],
                            a.edi_code,
                            b.edi_code,
                            t,
                        ):
                            continue
                        hit = r
                        break
                    if hit:
                        break
                if hit:
                    break
            if hit is None:
                continue
            severity, summary = "danger", "복합제에 들어 있는 성분이 함께 드시면 안 되는 약과 겹쳐요"
            if when == "recent":
                severity = DOWNGRADE[severity]
                summary = "복합제에 들어 있는 성분이 최근까지 드신 약과 함께 드시면 안 되는 성분이에요. 남은 약을 아직 드시고 있다면 함께 드시지 마세요"
            out.append(
                Warning(
                    "interaction",
                    severity,
                    (a.item_id, b.item_id),
                    summary,
                    reason=hit["reason"],
                    source="심평원 DUR 병용금기 (복합제 구성 성분 기준으로 추가 확인)",
                    notice_date=self._fmt_notice(hit["notice_date"]),
                    detail={**self._pair_label(a, b, name), "timing": when, "gap_days": gap, "basis": "component"},
                )
            )
        return out

    # ---- 노인주의
    def _elderly(self, oral, products, patient, today, t):
        out = super()._elderly(oral, products, patient, today, t)
        done = {w.item_ids for w in out}
        for it in oral:
            if (it.item_id,) in done:
                continue
            _, comp = self._codes(products, it)
            for code in sorted(comp):
                r = self._q(
                    "SELECT * FROM dur_elderly WHERE ingr_code=? AND ? BETWEEN valid_from AND valid_to", code, t
                )
                if r and self._age_may_match(patient, today, r[0]["age"], "세", ">="):
                    out.append(
                        Warning(
                            "elderly",
                            "caution",
                            (it.item_id,),
                            f"{r[0]['age']}세 이상 어르신은 주의해서 드셔야 하는 성분이 들어 있어요",
                            reason=r[0]["reason"],
                            source="심평원 DUR 노인주의 (복합제 구성 성분 기준으로 추가 확인)",
                            detail={"basis": "component"},
                        )
                    )
                    break
        return out

    # ---- 연령금기
    def _age_limit(self, oral, products, patient, today, t):
        out = super()._age_limit(oral, products, patient, today, t)
        done = {w.item_ids for w in out}
        for it in oral:
            if (it.item_id,) in done:
                continue
            own, comp = self._codes(products, it)
            for code in sorted(comp):
                hit = False
                for r in self._q(
                    "SELECT * FROM dur_age_limit WHERE ingr_code=? AND ? BETWEEN valid_from AND valid_to", code, t
                ):
                    if self._age_may_match(patient, today, r["age"], r["unit"], r["op"]):
                        out.append(
                            Warning(
                                "age",
                                "danger",
                                (it.item_id,),
                                f"{r['age']}{r['cond_text']}에게는 쓰지 않는 성분이 들어 있어요",
                                reason=r["reason"],
                                source="심평원 DUR 연령금기 (복합제 구성 성분 기준으로 추가 확인)",
                                notice_date=self._fmt_notice(r["notice_date"]),
                                detail={"age": r["age"], "unit": r["unit"], "op": r["op"], "basis": "component"},
                            )
                        )
                        hit = True
                        break
                if hit:
                    break
        return out
