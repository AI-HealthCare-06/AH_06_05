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
