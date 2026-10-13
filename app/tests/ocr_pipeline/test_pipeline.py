"""OCR 파이프라인 단위 시험 (DB · 네트워크 없음) — 저장해 둔 CLOVA 결과(가짜 처방전)로 확인"""

import json
from datetime import date

from app.services.ocr import clova, icd, numeric
from app.services.ocr.matcher import AMBIGUOUS, FOUND, NOT_FOUND, NameMatcher
from app.services.ocr.meta import parse_meta
from app.services.ocr.pipeline import read

PRODUCTS = [
    ("641900040", "노바스크정5밀리그람(암로디핀베실산염)_(6.944mg/1정)"),
    ("641900041", "노바스크정10밀리그람(암로디핀베실산염)_(13.89mg/1정)"),
    ("644300010", "다이아벡스정500밀리그램(메트포르민염산염)_(0.5g/1정)"),
    ("645600020", "리피토정10밀리그램(아토르바스타틴칼슘삼수화물)_(10.85mg/1정)"),
    ("648800030", "아스피린프로텍트정100밀리그람_(0.1g/1정)"),
]
CODES = {"I10": "본태성 고혈압", "L10": "천포창", "E11": "2형 당뇨병", "M545": "요통"}
SAMPLE = json.loads(clova.SAMPLE.read_text(encoding="utf-8"))
TODAY = date(2026, 10, 13)


def matcher() -> NameMatcher:
    return NameMatcher(PRODUCTS)


def test_sample_prescription_rows_and_numbers():
    res = read(SAMPLE, matcher(), CODES, today=TODAY)
    assert res.status == "ok"
    assert res.issued == date(2026, 10, 1) and res.birth == 1955 and res.meta_flags == []
    assert [r.decision.status for r in res.rows] == [FOUND] * 4
    assert [(r.dose, r.times, r.days) for r in res.rows] == [(1, 1, 30), (1, 2, 30), (1, 1, 30), (1, 1, 30)]
    assert [r.decision.candidates[0].edi_code for r in res.rows] == ["641900040", "644300010", "645600020", "648800030"]
    assert res.timing == "식후 30분 복용"
    assert not res.row_count_mismatch


def test_sample_disease_110_is_not_silently_fixed():
    res = read(SAMPLE, matcher(), CODES, today=TODAY)
    d110 = res.diseases[0]
    assert d110.raw == "110" and d110.status == icd.MANY and d110.value[:2] == ["I10", "L10"]
    assert not any(d.confirmed for d in res.diseases if d.raw == "110")


def test_icd_rules():
    assert icd.fix_one("I10", CODES) == (icd.NORMAL, "I10")
    assert icd.fix_one("M54.5", CODES) == (icd.NORMAL, "M545")
    assert icd.fix_one("l10", CODES)[0] == icd.MANY
    assert icd.fix_one("E1L", CODES) == (icd.FIXED, "E11")
    assert icd.fix_one("XYZ", CODES) == (icd.UNKNOWN, None)
    assert icd.fix_one("", CODES) == (icd.UNKNOWN, None)


def test_matcher_exact_typo_and_not_found():
    m = matcher()
    exact = m.decide("다이아벡스정 500mg(메트포르민염산염)")
    assert exact.status == FOUND and exact.candidates[0].edi_code == "644300010"
    typo = m.decide("리피토정10밀ㄹ그램(아토르바스타튼(칼슘삼수화물)")
    assert typo.status == FOUND and typo.candidates[0].edi_code == "645600020" and not typo.exact
    assert m.decide("병원").status == NOT_FOUND  # 너무 짧음
    assert m.decide("전혀다른이름의약입니다").status == NOT_FOUND


def test_matcher_exact_name_wins_and_look_alike_drugs_are_ambiguous():
    m = NameMatcher(
        [
            ("100000001", "가나다라마바아정10밀리그램"),
            ("100000002", "가나다라마바자정10밀리그램"),
            ("100000003", "가나다라마바아정5밀리그램"),
        ]
    )
    assert m.decide("가나다라마바아정10밀리그램").status == FOUND  # 글자 그대로 같으면 그 약
    # 같은 약의 다른 규격(5 · 10)은 후보가 둘이어도 헷갈리는 경우로 치지 않지만, 이름이 다른 약과 점수가 같으면 고르게 한다
    assert m.decide("가나다라마바사정10밀리그램").status == AMBIGUOUS


def test_matcher_empty_index():
    assert NameMatcher([]).decide("노바스크정5밀리그램").status == NOT_FOUND


def test_numeric_ranges():
    assert numeric.check(1, 3, 30) == []
    assert numeric.check(0.5, 1, 7) == []
    assert numeric.check(0.3, 7, 200) == ["1회량", "하루 횟수", "총 일수"]
    assert numeric.check(None, None, None) == []


def test_parse_meta_tolerant_and_strict():
    assert parse_meta("2O26년 1O월 01일 1955년생", TODAY)[:2] == (date(2026, 10, 1), 1955)
    assert parse_meta("2026.10.01 생년 1955", TODAY)[:2] == (date(2026, 10, 1), 1955)
    issued, birth, flags = parse_meta("2026년 13월 40일 1700년생", TODAY)
    assert issued is None and birth is None and len(flags) == 2
    assert parse_meta("2027년 1월 1일", TODAY)[0] is None  # 미래 교부일


def test_header_missing_or_empty_gives_retake():
    cut = json.loads(json.dumps(SAMPLE))
    cut["images"][0]["fields"] = [f for f in cut["images"][0]["fields"] if "일수" not in f["inferText"]]
    assert read(cut, matcher(), CODES).reason == "no_header"
    empty = {"images": [{"fields": []}]}
    assert read(empty, matcher(), CODES).status == "retake"
    assert read({}, matcher(), CODES).status == "retake"


# ── 실제 양식 5장 시험(10/13)에서 찾은 문제: 합성 글자 목록으로 재현 ──────────────────────────────
def _fld(text: str, x: float, y: float, w: float = 80, h: float = 24) -> dict:
    return {
        "inferText": text,
        "inferConfidence": 0.99,
        "boundingPoly": {
            "vertices": [{"x": x, "y": y}, {"x": x + w, "y": y}, {"x": x + w, "y": y + h}, {"x": x, "y": y + h}]
        },
    }


def _table(split_head: bool, tail: list[dict]) -> dict:
    head = (
        [_fld("투약", 380, 100, 40), _fld("량", 425, 100, 30), _fld("투여", 480, 100, 40), _fld("횟수", 525, 100, 40)]
        + [_fld("투약", 580, 100, 40), _fld("일수", 625, 100, 40)]
        if split_head
        else [_fld("투약량", 380, 100), _fld("투여횟수", 480, 100), _fld("총투약일수", 580, 100)]
    )
    rows = [_fld("명칭", 100, 100)] + head
    for i, (name, a, b, c) in enumerate((("돔페리돈", 1, 3, 2), ("라니티딘", 3, 2, 5))):
        y = 200 + i * 60
        rows += [_fld(name, 100, y), _fld(str(a), 400, y, 20), _fld(str(b), 500, y, 20), _fld(str(c), 600, y, 20)]
    return {"images": [{"fields": rows + tail}]}


def test_table_stops_at_end_markers():
    from app.services.ocr.table import parse_table

    tail = [
        _fld("조제시", 100, 700),
        _fld("참고사항", 200, 700),
        _fld("사용기간", 100, 900),
        _fld("교부일로부터", 300, 900),
    ]
    t = parse_table(_table(False, tail))
    assert t is not None
    assert [r.name for r in t.rows] == ["돔페리돈", "라니티딘"]
    assert t.rows[1].nums == [3.0, 2.0, 5.0]


def test_split_head_words_are_merged():
    from app.services.ocr.table import parse_table

    t = parse_table(_table(True, []))
    assert t is not None
    assert [r.nums for r in t.rows] == [[1.0, 3.0, 2.0], [3.0, 2.0, 5.0]]


def test_disease_label_split_and_notice_sentence():
    from app.services.ocr.table import join_code_boxes, parse_table

    notice = [_fld("※", 100, 400), _fld("환자의 요구가 있는 때에는 질병분류기호를 기재하지 아니합니다.", 100, 420, 600)]
    label = [_fld("질병", 100, 150), _fld("분류", 160, 150), _fld("기호", 220, 150), _fld("I219", 300, 150),
             _fld("처방", 380, 150), _fld("의료인의", 430, 150)]  # fmt: skip
    t = parse_table(_table(False, label + notice))
    assert t is not None and t.disease_raw == "I219"
    only_notice = parse_table(_table(False, notice))
    assert only_notice is not None and only_notice.disease_raw is None  # "를"을 코드로 읽지 않음
    assert join_code_boxes("A 1 2 3 B 2 3 4") == "A123 B234"
    assert join_code_boxes("I10 E11") == "I10 E11"


def test_issue_date_ignores_dispensing_date():
    from datetime import date

    from app.services.ocr.meta import parse_meta

    today = date(2026, 10, 13)
    issued, _b, flags = parse_meta("교부연월일 및 번호 20 년 월 일 제 호 조제연월일 2018.05.30", today)
    assert issued is None and "교부일 못 읽음" in flags
    issued, _b, _f = parse_meta("교부연월일 2022년 12월 1일 제113호 조제연월일 2021 12 1", today)
    assert issued == date(2022, 12, 1)
    issued, _b, _f = parse_meta("교부번호 2018 년 08 월 07 일 조제년월일 2018.08.09", today)
    assert issued == date(2018, 8, 7)
