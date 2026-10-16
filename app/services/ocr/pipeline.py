"""처방전 OCR 파이프라인: CLOVA 결과 한 장 → 사용자 확인 화면에 쓸 정보 (DB · 네트워크 없음)

(1) prepare 기울임 바로잡기 · 숫자 칸 정리 → (2) table 표 읽기 → (3) meta 교부일 · 출생연도
→ (4) icd 질병분류기호 보정 → (5) matcher 약 이름 맞추기 (못 찾으면 자모 조각으로 비슷한 이름 추천) → (6) numeric 숫자 범위 검사
상태가 "retake"이면 사진을 다시 찍게 한다 (reason: tilt | no_header | no_rows).
"""

import re
from collections.abc import Container
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from app.services.ocr import icd, numeric, prepare
from app.services.ocr.mask_layout import join_masked
from app.services.ocr.matcher import AMBIGUOUS, FOUND, NOT_FOUND, Decision, NameMatcher
from app.services.ocr.meta import parse_meta
from app.services.ocr.pouch import dispensed_date, parse_pouch
from app.services.ocr.pouch_panel import panel_words, refine
from app.services.ocr.table import parse_table

SUGGESTED_SIMILAR = "similar"  # RowRead.suggested_by 값 (LLM 추천은 "llm")
SIMILAR_FLAG = (
    "비슷한 이름을 추천"  # 글자가 달라서 규칙이 못 찾았지만 자모 조각이 비슷한 약을 후보로 올림 (사용자가 고름)
)
SIBLING_FLAG = (
    "이름이 비슷한 다른 약이 있어요"  # 글자 하나 차이의 다른 성분 약이 있어 사용자가 고름 (matcher.decide의 siblings)
)
PANEL_FLAG = "약품명 칸의 이름으로 바로잡았어요"  # 약봉투 영수증 칸 이름이 잘리거나 잘못 읽혀서, 오른쪽 "약품명" 칸의 같은 약 이름으로 바꿈 (pouch_panel)
CUT_FLAG = "약 이름이 잘려 있어요"  # 약봉투 카드가 긴 이름을 "···"로 줄인 경우: 함량 등 뒷부분이 없어 자동으로 정하지 않고 사용자가 고름
LOW_CONF_FLAG = (
    "약 이름 글자가 흐리게 읽혔어요"  # CLOVA가 이름 글자를 낮은 확신으로 읽음: 이름이 맞게 읽혔는지 사용자가 확인
)
LOW_CONF = 0.5  # 이름 글자 평균 신뢰도가 이보다 낮으면 자동으로 정하지 않는다 (저장해 둔 실제 결과에서 이 아래로 맞게 읽힌 이름은 r2의 레마이드정 한 줄(0.43)뿐이었다)
NUMS_FLAG = "숫자가 어느 약 줄의 것인지 확실하지 않아요"  # 처방전 표에서 숫자 줄이 두 약 줄의 한가운데쯤에 있음: 이웃 약의 숫자와 바뀌었을 수 있어 사용자가 확인
UNSURE_FLAG = "약 이름 줄이 확실하지 않아요"  # 약봉투에서 이름 줄을 위치가 아닌 글자 크기로 골랐을 때: 사진이 흔들려 이름과 성분이 헷갈렸을 수 있어 사용자가 확인
HEADERLESS_FLAG = "표 머리글이 없어 칸 순서를 추정했어요 (1회량 · 하루 횟수 · 총 일수)"  # 약봉투 목록에 머리글이 없을 때: 숫자가 어느 칸인지 사용자가 확인 (약 줄은 모두 사용자 확인으로 넘김)
ICD_CONF = 0.95  # 질병분류기호 글자의 확실도가 이보다 낮으면 보정 결과와 상관없이 사용자가 고르게 한다


@dataclass
class DiseaseRead:
    raw: str
    status: str  # icd.NORMAL | FIXED | MANY | UNKNOWN
    value: str | list[str] | None
    conf: float
    confirmed: bool  # True면 사용자 확인 없이 그대로 씀 (상병마스터에 있고 글자 확실도도 높음)


@dataclass
class RowRead:
    read_name: str
    decision: Decision
    dose: float | None
    times: float | None
    days: float | None
    flags: list[str] = field(default_factory=list)
    suggested_by: str | None = (
        None  # 후보가 추천에서 왔을 때: similar(비슷한 이름) | llm — 화면이 "추천"임을 알리는 데 씀
    )
    guide: list[str] = field(
        default_factory=list
    )  # 약봉투: 약국이 약 아래에 인쇄한 복약 안내 (마스킹 전 · 저장할 때 mask)


@dataclass
class OcrRead:
    status: str  # ok | retake
    reason: str | None = None  # retake일 때: tilt | no_header | no_rows (머리글은 찾았는데 약 줄이 하나도 없음)
    doc_type: str = "prescription"  # prescription | pill_bag (처방전 표를 못 읽고 약봉투 표를 읽었을 때)
    issued: date | None = None
    birth: int | None = None
    meta_flags: list[str] = field(default_factory=list)
    hospital_name: str | None = None
    timing: str | None = None  # 처방전 아래쪽 "용법" 문구 (모든 약 공통)
    confidence: float | None = None
    row_count_mismatch: bool = False
    diseases: list[DiseaseRead] = field(default_factory=list)
    rows: list[RowRead] = field(default_factory=list)
    raw_text: str = ""


def _hospital(text: str) -> str | None:
    m = re.search(r"의료기관\s*명칭\s*(.+?)\s*(?:환자|전화번호|성명)", text)
    name = m[1].strip() if m else ""
    return name[:200] or None


def _timing(text: str) -> str | None:
    m = re.search(r"용법\s*[:：]?\s*(.+?)\s*(?:사용기간|※|$)", text)
    t = m[1].strip() if m else ""
    return t[:50] or None


def read(  # noqa: C901
    data: dict[str, Any], matcher: NameMatcher, codes: Container[str], today: date | None = None
) -> OcrRead:
    try:
        fields = data["images"][0]["fields"]
    except (KeyError, IndexError, TypeError):
        return OcrRead(status="retake", reason="no_header")
    if not fields:
        return OcrRead(status="retake", reason="no_header")
    try:
        prep, _angle, _removed, st = prepare.prepare(data)
        if st == "too_tilted":
            return OcrRead(status="retake", reason="tilt")
        table = parse_table(prep)
        pouch = table is None
        if (
            pouch
        ):  # 처방전 머리글이 없으면 약봉투 표(투약량 · 횟수 · 일수)로 다시 본다. 기울기를 바로잡은 위치(prep)로 읽는다
            table = parse_pouch(prep)
    except (KeyError, IndexError, TypeError, ValueError, ZeroDivisionError):
        return OcrRead(status="retake", reason="no_header")  # 글자 목록 모양이 이상함 → 읽을 수 없는 사진으로 본다
    if table is None:
        return OcrRead(status="retake", reason="no_header")
    if not table.rows:
        # 머리글만 찾고 약 줄을 하나도 못 읽었다. 약이 없는 처방전으로 저장하면 사용자는 빈 목록을 보게 되므로 다시 찍게 한다
        return OcrRead(status="retake", reason="no_rows")

    pfields = prep["images"][0]["fields"]
    text = " ".join(f["inferText"] for f in pfields)
    if pouch:
        # 약봉투에는 교부일 · 병원 · 출생연도가 없다. 영수증 띠의 날짜 · 약국 이름을 교부일 · 병원으로 읽지 않도록 조제일만 읽는다
        issued, mflags = dispensed_date(pfields, today)
        birth = None
    else:
        issued, birth, mflags = parse_meta(text, today)
    confs = [f["inferConfidence"] for f in pfields if "inferConfidence" in f]
    out = OcrRead(
        status="ok",
        doc_type="pill_bag" if pouch else "prescription",
        issued=issued,
        birth=birth,
        meta_flags=mflags,
        hospital_name=None if pouch else _hospital(text),
        timing=None if pouch else _timing(text),
        confidence=round(sum(confs) / len(confs), 4) if confs else None,
        # 숫자 칸 중 가장 많이 읽힌 칸의 숫자 수와 약 줄 수가 다르면 줄 나누기가 틀렸을 수 있다
        row_count_mismatch=table.n_anchor >= 2 and len(table.rows) != table.n_anchor,
        raw_text=join_masked(pfields),  # 저장하지 않는 값 (10/15). 이름 칸은 위치로 가려 둔다
    )

    if table.disease_raw:
        i0 = next((i for i, f in enumerate(pfields) if re.search(r"질병\s*분류\s*기호|^기호$", f["inferText"])), None)
        seg: list[float] = []
        if i0 is not None:
            for f in pfields[i0 + 1 : i0 + 6]:
                if "면허" in f["inferText"]:
                    break
                seg.append(f["inferConfidence"])
        dzconf = min(seg, default=1.0)
        for raw, stt, value in icd.fix_field(table.disease_raw, codes):
            out.diseases.append(
                DiseaseRead(raw, stt, value, round(dzconf, 2), stt == icd.NORMAL and dzconf >= ICD_CONF)
            )

    if table.headerless:
        out.meta_flags.append(HEADERLESS_FLAG)

    panel = panel_words(pfields) if pouch else []
    for r in table.rows:
        dose, times, days = r.nums
        flags = [
            f"{label} 못 읽음" for label, v in (("1회량", dose), ("하루 횟수", times), ("총 일수", days)) if v is None
        ]
        flags += [f"{x} 범위 밖" for x in numeric.check(dose, times, days)]
        name = r.name
        decision = matcher.decide(name)
        fixed = False
        if panel and (
            decision.status != FOUND
            or name.count("(") > name.count(")")
            or r.cut
            or (r.conf is not None and r.conf < LOW_CONF)
        ):
            # 영수증 칸 이름을 믿기 어려울 때만 오른쪽 "약품명" 칸의 이름으로 바꾼다 (이미 잘 찾은 이름은 그대로 둠)
            if (better := refine(name, panel)) and better != name:
                new = matcher.decide(better)
                same = decision.status == FOUND and [c.edi_code for c in new.candidates[:1]] == [
                    c.edi_code for c in decision.candidates[:1]
                ]
                name, decision, fixed = better, new, True
                if not same:  # 이미 같은 약을 찾았으면 이름만 깨끗하게 바꾸고 표시는 붙이지 않는다
                    flags.append(PANEL_FLAG)
        # 머리글 없는 목록은 숫자가 어느 칸인지 추정한 것이고 글자도 흐린 경우가 많아, 자동으로 정하지 않고 줄마다 사용자가 확인한다
        for unsure, flag in (
            (r.cut and not fixed, CUT_FLAG),
            (r.unsure, UNSURE_FLAG),
            (r.nums_unsure, NUMS_FLAG),
            (r.conf is not None and r.conf < LOW_CONF and not fixed, LOW_CONF_FLAG),
            (table.headerless, HEADERLESS_FLAG),
        ):
            if not unsure:
                continue
            flags.append(flag)
            # 잘린 이름은 우연히 한 약과만 맞아도 다른 함량일 수 있고, 이름 줄이 불확실하면 성분 줄을 읽었을 수 있다 → 후보로 올려 사용자가 고름
            if decision.status == FOUND:
                decision = Decision(AMBIGUOUS, decision.score, decision.candidates, sibling=decision.sibling)
        if decision.sibling:
            flags.append(SIBLING_FLAG)
        suggested_by = None
        if decision.status == NOT_FOUND and (similar := matcher.similar(name)) is not None:
            # 사용자가 고르는 후보로만 올린다 (자동 확정 아님). 저장할 때 match_score는 비운다 (suggested_by 참고)
            decision = similar
            flags.append(SIMILAR_FLAG)
            suggested_by = SUGGESTED_SIMILAR
        out.rows.append(RowRead(name, decision, dose, times, days, flags, suggested_by, list(r.guide)))
    return out
