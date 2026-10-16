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
    assert icd.fix_one("M54S", CODES) == (icd.FIXED, "M545")  # 네 번째 글자(5)를 S로 읽음 — 세 번째 글자 뒤도 숫자 자리
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


# ── 실제 CLOVA 결과 9장(10/13 저장본)으로 다시 시험하며 찾은 문제: 같은 모양을 합성 글자 목록으로 재현 ──────────
def _dense(h: float = 15, pitch: float = 19) -> list[dict]:
    """줄 간격이 글자 높이와 비슷하게 촘촘한 사진(너비 700px 안팎) + 표 오른쪽 '용' '법' 머리글"""
    f = [_fld("명칭", 160, 341, 26, h), _fld("투약량", 224, 351, 41, h), _fld("투여횟수", 291, 351, 53, h),
         _fld("투약일수", 367, 351, 52, h), _fld("용", 501, 341, 15, h), _fld("법", 546, 341, 12, h)]  # fmt: skip
    for i, (n, a, b, c) in enumerate((("돔페리돈", 1, 3, 2), ("라니티딘", 3, 2, 5), ("록소프로펜", 2, 4, 7))):
        y = 372 + i * pitch
        f += [
            _fld(n, 103, y, 53, h),
            _fld(str(a), 239, y, 10, 12),
            _fld(str(b), 313, y, 8, 12),
            _fld(str(c), 387, y, 11, 12),
        ]
    return [{"images": [{"fields": f}]}][0]["images"][0]["fields"]  # type: ignore[no-any-return]


def test_dense_rows_are_not_merged_and_right_side_header_is_not_a_row():
    from app.services.ocr.table import parse_table

    t = parse_table({"images": [{"fields": _dense()}]})
    assert t is not None
    assert [r.name for r in t.rows] == ["돔페리돈", "라니티딘", "록소프로펜"]  # '용' '법'이 약 줄이 되지 않음
    assert [r.nums for r in t.rows] == [[1.0, 3.0, 2.0], [3.0, 2.0, 5.0], [2.0, 4.0, 7.0]]


def test_numbers_read_out_of_list_order_and_biased_columns():
    from app.services.ocr.table import parse_table

    fs = _dense()
    days = [f for f in fs if f["inferText"] in {"2", "5", "7"} and f["boundingPoly"]["vertices"][0]["x"] == 387]
    rest = [f for f in fs if f not in days]
    fs = days + rest  # 총 일수가 맨 앞 번호로 나옴 (머리글보다 앞)
    t = parse_table({"images": [{"fields": fs}]})
    assert t is not None and [r.nums[2] for r in t.rows] == [2.0, 5.0, 7.0]
    # 1회량 숫자가 횟수 칸 쪽으로 치우쳐도 한 줄에 숫자가 3개면 왼쪽부터 순서대로
    for f in fs:
        if f["inferText"] in {"1", "3", "2"} and f["boundingPoly"]["vertices"][0]["x"] == 239:
            for v in f["boundingPoly"]["vertices"]:
                v["x"] += 30
    t2 = parse_table({"images": [{"fields": fs}]})
    assert t2 is not None and [r.nums[0] for r in t2.rows] == [1.0, 3.0, 2.0]


def test_head_variants_split_across_boxes():
    from app.services.ocr.table import parse_table

    fs = [_fld("명칭", 160, 341, 26, 15), _fld("투여량", 224, 351, 41, 15), _fld("일투어", 291, 341, 40, 15),
          _fld("횟수", 296, 351, 30, 15), _fld("총투약", 367, 341, 40, 15), _fld("일수", 372, 351, 30, 15),
          _fld("돔페리돈", 103, 372, 53, 15), _fld("1", 239, 372, 10, 12), _fld("3", 313, 372, 8, 12), _fld("2", 387, 372, 11, 12)]  # fmt: skip
    t = parse_table({"images": [{"fields": fs}]})  # "일투어+횟수", "총투약+일수"로 쪼개져 읽힘
    assert t is not None and t.rows[0].nums == [1.0, 3.0, 2.0]


def test_end_marker_read_one_character_at_a_time():
    from app.services.ocr.table import parse_table

    fs = _dense() + [_fld(c, 144 + i * 22, 449, 15, 15) for i, c in enumerate("이하여백")]
    t = parse_table({"images": [{"fields": fs}]})
    assert t is not None and [r.name for r in t.rows] == ["돔페리돈", "라니티딘", "록소프로펜"]


def test_edi_code_starts_each_drug_even_when_name_wraps():
    from app.services.ocr.table import parse_table

    fs = [_fld("명칭", 160, 280, 26, 13), _fld("투여량", 278, 282, 41, 12), _fld("투여횟수", 323, 282, 30, 11),
          _fld("총투약일수", 358, 282, 52, 11)]  # fmt: skip
    for i, (code, n1, n2, nums) in enumerate(
        (("645404010", "엘로시드", "제일약품(주)", (1, 2, 7)), ("645404500", "넥실렌", "제일약품(주)", (1, 2, 7)))
    ):
        y = 300 + i * 30
        fs += [_fld(code, 33, y, 50, 11), _fld(n1, 88, y, 60, 13), _fld(n2, 39, y + 14, 60, 13)]
        fs += [_fld(str(v), x, y + 12, 8, 10) for v, x in zip(nums, (290, 333, 372), strict=True)]
    t = parse_table({"images": [{"fields": fs}]})
    assert t is not None and [r.name for r in t.rows] == ["엘로시드제일약품(주)", "넥실렌제일약품(주)"]
    assert [r.nums for r in t.rows] == [[1.0, 2.0, 7.0]] * 2


def test_disease_codes_after_short_label_and_spaced_stop_word():
    from app.services.ocr.table import parse_table

    # "분류 기호 B 2 3 4 질병 A 1 2 3 처방" (줄마다 코드가 따로)
    lab = [
        _fld(w, 100 + i * 40, 150, 30, 15)
        for i, w in enumerate(["분류", "기호", "B", "2", "3", "4", "질병", "A", "1", "2", "3", "처방"])
    ]
    t = parse_table({"images": [{"fields": _dense() + lab}]})
    assert t is not None and t.disease_raw == "B234 A123"
    # "질병 분류 기호 처 방 의료인의" 처럼 값이 비어 있으면 '처'를 코드로 읽지 않음
    empty = [_fld(w, 100 + i * 40, 150, 30, 15) for i, w in enumerate(["질병", "분류", "기호", "처", "방", "의료인의"])]
    t2 = parse_table({"images": [{"fields": _dense() + empty}]})
    assert t2 is not None and t2.disease_raw is None


def test_disease_codes_found_by_position_when_listed_before_label():
    from app.services.ocr.table import parse_table

    # 라벨이 세로로 쌓여 있고(왼쪽), 코드 숫자는 오른쪽에 두 줄(숫자만): 글자 목록에서는 코드가 라벨보다 앞 번호
    code = [_fld(c, 123 + i * 43, 243, 12, 18) for i, c in enumerate("109")] + [
        _fld(c, 123 + i * 43, 271, 12, 18) for i, c in enumerate("499")
    ]
    label = [_fld("질병", 29, 241, 40, 18), _fld("분류", 29, 258, 40, 18), _fld("기호", 29, 272, 40, 18)]
    stop = [_fld("처", 286, 240, 15, 18), _fld("방", 315, 240, 15, 18), _fld("의료인의", 284, 255, 60, 18)]
    t = parse_table({"images": [{"fields": code + label + stop + _dense()}]})
    assert t is not None and t.disease_raw == "109 499"


# ── 약봉투(10/15 샘플 p2): 영수증 쪽에 떨어져 있는 "투약일수"를 표 머리글로 보면 이름 · 주소가 약 줄이 되어 저장된다 ──────
def _pouch_strip() -> list[dict]:
    return [
        _fld("환자", 16, 34, 20, 9), _fld("성명", 36, 34, 20, 9), _fld("홍길동", 58, 32, 24, 9),
        _fld("투약일수", 104, 24, 25, 8), _fld("3", 133, 22, 6, 7),
        _fld("서울시", 59, 162, 16, 9), _fld("영등포구", 75, 162, 22, 9),
    ]  # fmt: skip


def test_lone_days_word_in_receipt_strip_is_not_a_table_head():
    from app.services.ocr.table import parse_table

    data = {"images": [{"fields": _pouch_strip()}]}
    assert parse_table(data) is None
    res = read(data, matcher(), CODES)
    assert (res.status, res.reason) == ("retake", "no_header")
    assert res.rows == []  # 환자 이름 · 주소가 약 줄로 새지 않는다


def test_real_head_wins_over_lone_days_word_and_prepare_keeps_tokens():
    from app.services.ocr import prepare
    from app.services.ocr.table import parse_table

    real = _table(False, [])["images"][0]["fields"]
    data = {"images": [{"fields": _pouch_strip() + real}]}
    prep = prepare.prepare(data)[0]
    assert prepare.find_head(prep["images"][0]["fields"]) is not None
    t = parse_table(prep)
    assert t is not None and [(r.name, r.nums) for r in t.rows] == [
        ("돔페리돈", [1.0, 3.0, 2.0]),
        ("라니티딘", [3.0, 2.0, 5.0]),
    ]  # 열 위치도 진짜 머리글 줄에서 잡는다 (영수증 쪽 "투약일수" 위치로 잡으면 약 이름이 칸 밖으로 밀려 줄이 사라진다)
    assert prepare.find_head(_pouch_strip()) is None
    assert prepare.prepare({"images": [{"fields": _pouch_strip()}]})[2] == 0  # 가짜 머리글로는 숫자 칸을 지우지 않는다


# ── 10/15 s1 사진: 약이 1개뿐인 처방전이 0줄로 저장되던 문제 ───────────────────────────────────
def _s1_like(order_yongbeop_first: bool) -> dict:
    """머리글 오른쪽 "용법" 칸이 약 줄보다 앞 번호로 읽히고, 이름 옆 "(제일)"이 따로 읽힌 처방전"""
    head = [_fld("명칭", 100, 100), _fld("투약량", 380, 100), _fld("투여횟수", 480, 100), _fld("총투약일수", 580, 100)]
    yong = [_fld("용법", 700, 100, 40)]
    body = [
        _fld("스타브론정12.5MG", 100, 200, 160),
        _fld("(제일)", 270, 200, 50),  # 같은 줄에서 따로 읽힌 제조사 표시
        _fld("1", 400, 200, 20),
        _fld("3", 500, 200, 20),
        _fld("7", 600, 200, 20),
    ]
    tail = [_fld("용법", 100, 400, 40), _fld("식후", 150, 400, 40)]  # 표 아래의 진짜 "용법:" 문구
    fields = head + (yong + body if order_yongbeop_first else body + yong) + tail
    return {"images": [{"fields": fields}]}


def test_header_yongbeop_column_does_not_cut_the_drug_rows():
    from app.services.ocr.table import parse_table

    for first in (True, False):
        t = parse_table(_s1_like(first))
        assert t is not None and len(t.rows) == 1, first
        assert t.rows[0].nums == [1.0, 3.0, 7.0]


def test_name_pieces_on_the_same_line_are_one_drug():
    from app.services.ocr.table import parse_table

    t = parse_table(_s1_like(False))
    assert t is not None and [r.name for r in t.rows] == ["스타브론정12.5MG(제일)"]


def test_two_drugs_on_different_lines_still_split():
    from app.services.ocr.table import parse_table

    t = parse_table(_table(False, []))
    assert t is not None and [r.name for r in t.rows] == ["돔페리돈", "라니티딘"]


def test_header_without_any_drug_row_is_a_retake_not_an_empty_prescription():
    fields = [f for f in _table(False, [])["images"][0]["fields"] if f["boundingPoly"]["vertices"][0]["y"] < 150]
    res = read({"images": [{"fields": fields}]}, matcher(), CODES, today=TODAY)
    assert res.status == "retake" and res.reason == "no_rows" and res.rows == []


def test_notices_keep_reading_flags_the_user_should_see():
    from app.services.ocr.pipeline import OcrRead
    from app.services.prescriptions import ROW_COUNT_NOTICE, notices_of

    assert notices_of(OcrRead(status="ok")) is None
    only_birth = OcrRead(status="ok", meta_flags=["출생연도 못 읽음", "출생연도 범위 밖"])
    assert notices_of(only_birth) is None  # 출생연도는 저장하지 않으니 알리지 않는다
    r = OcrRead(status="ok", meta_flags=["교부일 못 읽음", "출생연도 못 읽음"], row_count_mismatch=True)
    assert notices_of(r) == ["교부일 못 읽음", ROW_COUNT_NOTICE]


# ── 10/15: 이름 글자를 낮은 확신으로 읽었으면 자동으로 정하지 않는다 ────────────────────────────
def _one_drug(name: str, conf: float) -> dict:
    head = [_fld("명칭", 100, 100), _fld("투약량", 380, 100), _fld("투여횟수", 480, 100), _fld("총투약일수", 580, 100)]
    name_f = _fld(name, 100, 200, 160)
    name_f["inferConfidence"] = conf
    nums = [_fld("1", 400, 200, 20), _fld("3", 500, 200, 20), _fld("7", 600, 200, 20)]
    return {"images": [{"fields": head + [name_f] + nums}]}


def test_low_confidence_name_is_not_auto_matched():
    from app.services.ocr.pipeline import LOW_CONF_FLAG

    clear = read(_one_drug("노바스크정5밀리그람", 0.95), matcher(), CODES, today=TODAY).rows[0]
    assert clear.decision.status == FOUND and LOW_CONF_FLAG not in clear.flags

    blurry = read(_one_drug("노바스크정5밀리그람", 0.40), matcher(), CODES, today=TODAY).rows[0]
    assert blurry.decision.status == AMBIGUOUS and LOW_CONF_FLAG in blurry.flags  # 후보로만 올리고 사용자가 고른다


def test_confidence_just_at_the_limit_is_still_auto_matched():
    from app.services.ocr.pipeline import LOW_CONF, LOW_CONF_FLAG

    r = read(_one_drug("노바스크정5밀리그람", LOW_CONF), matcher(), CODES, today=TODAY).rows[0]
    assert r.decision.status == FOUND and LOW_CONF_FLAG not in r.flags


# ── 10/15 약 이름 맞추기 점검: 실제 급여목록(22,045개)으로 재다가 찾은 문제 ─────────────────────────
def test_unit_symbols_in_the_master_do_not_decide_which_strength_matches():
    # 급여목록 이름 234개는 "㎎" 같은 호환 문자를 쓴다. 통일하지 않으면 "500mg"로 읽은 약이 250mg로 확정됐다
    m = NameMatcher(
        [
            (
                "1",
                "데파코트서방정250mg(디발프로엑스나트륨)_(0.2691g/1정)",
            ),  # 이쪽은 mg, 500은 ㎎ (실제 급여목록이 이렇게 섞여 있다)
            ("2", "데파코트서방정500㎎(디발프로엑스나트륨)_(0.5381g/1정)"),
        ]
    )
    d = m.decide("데파코트서방정500mg(디발프로엑스나트륨)")
    assert d.status == FOUND and d.candidates[0].edi_code == "2"
    d = m.decide("데파코트서방정500㎎(디발프로엑스나트륨)")
    assert d.status == FOUND and d.candidates[0].edi_code == "2"


def test_a_name_in_the_master_wins_over_a_name_with_the_same_letter_pairs():
    # "브록솔정(암브록솔염산염)"과 "록솔정(암브록솔염산염)"은 2글자 조각 집합이 같아 점수가 같다 — 글자 그대로 같은 쪽이 맞는 약이다
    m = NameMatcher(
        [
            ("9", "록솔정(암브록솔염산염)_(30mg/1정)"),  # 번호가 더 커서 동점이면 이쪽이 먼저 나오던 쪽
            ("1", "브록솔정(암브록솔염산염)_(30mg/1정)"),
        ]
    )
    d = m.decide("브록솔정(암브록솔염산염)_(30mg/1정)")
    assert d.status == FOUND and d.candidates[0].edi_code == "1"


def test_three_letter_names_are_found_only_when_they_match_exactly():
    # 급여목록에는 울셋정 · 코푸정처럼 3글자 이름이 실제로 있다 (이전에는 4글자 미만이면 무조건 못 찾음)
    m = NameMatcher(
        [
            ("1", "울셋정(트라마돌염산염)_(37.5mg/1정)"),
            ("2", "코푸정_(1정)"),
            ("3", "울셋서방정(트라마돌)_(1정)"),
            ("4", "티씰_(1병)"),
        ]
    )
    d = m.decide("코푸정")
    assert d.status == FOUND and d.candidates[0].edi_code == "2"
    assert (
        m.decide("티씰").status == NOT_FOUND
    )  # 목록에 정확히 있어도 2글자는 안 찾는다 (병원 · 약국 같은 낱말이 섞일 수 있음)
    assert m.decide("코푼정").status == NOT_FOUND  # 비슷한 이름으로는 3글자를 확정하지 않는다
    assert m.decide("병원").status == NOT_FOUND


def test_a_misread_strength_is_not_auto_matched_to_another_strength():
    # 한 자리를 잘못 읽어도 글자는 거의 같아 점수가 높다. 함량 숫자가 다르면 사용자가 고르게 한다 (급여목록으로 시험: 1,500개 중 49개가 다른 함량으로 확정됐었다)
    m = NameMatcher(
        [
            ("1", "피엠에스로수바스타틴정20밀리그램(로수바스타틴칼슘)_(20.838mg/1정)"),
            ("2", "피엠에스로수바스타틴정10밀리그램(로수바스타틴칼슘)_(10.4mg/1정)"),
            ("3", "피엠에스로수바스타틴정5밀리그램(로수바스타틴칼슘)_(5.2mg/1정)"),
        ]
    )
    ok = m.decide("피엠에스로수바스타틴정5밀리그램")
    assert ok.status == FOUND and ok.candidates[0].edi_code == "3" and not ok.strength
    assert m.decide("피엠에스로수바스타틴정5mg").status == FOUND  # 표기만 다름(mg)은 그대로 확정
    for misread in ("피엠에스로수바스타틴정2밀리그램", "피엠에스로수바스타틴정50밀리그램"):
        d = m.decide(misread)
        assert d.status == AMBIGUOUS, (
            misread
        )  # (50은 20 · 5와 점수가 비슷해 동점 규칙으로도 걸리고, 2는 함량 규칙으로 걸린다)
        assert {"1", "2", "3"} >= {c.edi_code for c in d.candidates} and d.candidates  # 사용자가 고를 후보가 있다
    assert m.decide("피엠에스로수바스타틴정2밀리그램").strength  # 목록에 없는 함량: 가장 가까운 약으로 확정하지 않는다
    assert not m.decide("피엠에스로수바스타틴정").strength  # 숫자가 없으면 이 규칙은 쓰지 않는다


def test_strength_with_slash_and_decimal_numbers_compares_every_number():
    m = NameMatcher(
        [
            ("1", "엔피포지정10/160밀리그램_(1정)"),
            ("2", "엔피포지정5/160밀리그램_(1정)"),
            ("3", "온글라이자정2.5밀리그램(삭사글립틴수화물)_(1정)"),
        ]
    )
    assert m.decide("엔피포지정5/160밀리그램").status == FOUND
    assert m.decide("엔피포지정1/160밀리그램").status == AMBIGUOUS  # 10/160의 앞 숫자를 한 자리 놓침
    assert m.decide("온글라이자정2.5밀리그램").status == FOUND
    assert m.decide("온글라이자정5밀리그램").status == AMBIGUOUS


def test_per_unit_quantity_after_strength_is_not_counted_as_a_strength_number():
    # 처방전에 "100mg/1정"처럼 1정당 함량이 붙어 읽히는 양식이 있다 (실제 샘플 r5). 이 1을 함량으로 세면 맞게 읽은 약도 확인 필요가 된다
    m = NameMatcher([("1", "명문아스피린장용정100mg_(0.1g/1정)"), ("2", "하원아스피린장용정100mg_(0.1g/1정)")])
    d = m.decide("명문아스피린장용정100mg/1정")
    assert d.status == FOUND and d.candidates[0].edi_code == "1" and not d.strength
    m2 = NameMatcher([("1", "엔피포지정5/160밀리그램_(1정)"), ("2", "엔피포지정10/160밀리그램_(1정)")])
    assert m2.decide("엔피포지정5/160밀리그램/1정").status == FOUND  # 뒤의 /1정만 빼고 5/160은 그대로 비교
    assert m2.decide("엔피포지정1/160밀리그램").status == AMBIGUOUS  # 단위 없는 뒤 숫자(복합제)는 계속 센다


def test_misread_short_text_near_a_number_column_is_removed_even_with_a_yongbeop_header_column():
    # 머리글 오른쪽의 "용법" 칸이 표 끝으로 잡히면 숫자 칸 근처의 잘못 읽힌 글자("l")가 지워지지 않아 약 줄이 하나 더 생긴다
    for yongbeop_first in (True, False):
        d = _s1_like(yongbeop_first)
        fields = d["images"][0]["fields"]
        fields.insert(
            len(fields) - 2, _fld("l", 395, 260, 12)
        )  # 1회 투약량 칸 아래의 "1"을 잘못 읽은 글자 (표 아래 "용법:" 문구 앞)
        from app.services.ocr import prepare as prep

        out, _ang, removed, status = prep.prepare(d)
        assert status == "ok" and removed == 1, yongbeop_first
        assert all(f["inferText"] != "l" for f in out["images"][0]["fields"])


# ── 10/15: 사진 해상도가 달라도 같은 결과 ───────────────────────────────────────────────────────
def _scaled(data: dict, k: float) -> dict:
    out = json.loads(json.dumps(data))
    for f in out["images"][0]["fields"]:
        for v in f["boundingPoly"]["vertices"]:
            v["x"] *= k
            v["y"] *= k
    return out


def test_result_does_not_depend_on_photo_resolution():
    # 표 읽기의 거리 기준이 픽셀 값이라 같은 처방전이 해상도에 따라 다르게(조용히 틀리게) 읽혔다: 샘플 좌표를 1.5배로 키우면 하루 횟수가 바뀜
    base = _table(False, [])
    expected = [("돔페리돈", 1.0, 3.0, 2.0), ("라니티딘", 3.0, 2.0, 5.0)]
    for k in (0.5, 1.0, 1.5, 2.5, 4.0):
        res = read(_scaled(base, k), matcher(), CODES, today=TODAY)
        assert res.status == "ok", k
        assert [(r.read_name, r.dose, r.times, r.days) for r in res.rows] == expected, k


def test_pouch_result_does_not_depend_on_photo_resolution():
    from app.tests.ocr_pipeline.test_pouch import card, card_table, data, head, strip

    base = data(head() + strip() + card_table(card(200, "알마겔정"), card(300, "리피토정10mg", ("2", "1", "7"))))
    seen = set()
    for k in (0.6, 1.0, 1.7, 3.0):
        t = read(_scaled(base, k), matcher(), CODES, today=TODAY)
        seen.add(tuple((r.read_name, r.dose, r.times, r.days) for r in t.rows))
    assert len(seen) == 1 and len(next(iter(seen))) == 2


def test_sample_prescription_reads_the_same_at_any_resolution():
    # 저장소에 있는 가짜 처방전(1,093 × 1,653)으로: 4배로 키우면(휴대폰 원본 크기) 정규화 없이는 네 줄의 숫자가 모두 달라졌다
    def rows(k: float):
        res = read(_scaled(SAMPLE, k), matcher(), CODES, today=TODAY)
        return res.status, [(r.read_name, r.dose, r.times, r.days) for r in res.rows], res.issued

    base = rows(1.0)
    assert base[0] == "ok" and len(base[1]) == 4
    for k in (0.5, 2.0, 3.0, 4.0):
        assert rows(k) == base, k


# ── 10/15: 숫자 줄이 두 약 줄의 한가운데에 있으면 사용자가 확인한다 ──────────────────────────────
def _two_drugs(num_dy: float) -> dict:
    """약 이름 줄 둘(y 200 · 260)과 그 숫자. 숫자는 이름 줄에서 num_dy만큼 아래에 있다 (30이면 두 이름의 한가운데)"""
    head = [_fld("명칭", 100, 100), _fld("투약량", 380, 100), _fld("투여횟수", 480, 100), _fld("총투약일수", 580, 100)]
    body = []
    for y, name, nums in ((200, "노바스크정5밀리그람", (1, 1, 30)), (260, "리피토정10밀리그램", (1, 1, 7))):
        body.append(_fld(name, 100, y, 200))
        body += [_fld(str(v), x, y + num_dy, 20) for x, v in zip((400, 500, 600), nums, strict=True)]
    return {"images": [{"fields": head + body}]}


def test_numbers_halfway_between_two_drugs_are_confirmed_by_the_user():
    from app.services.ocr.pipeline import NUMS_FLAG

    clear = read(_two_drugs(0), matcher(), CODES, today=TODAY)
    assert [r.decision.status for r in clear.rows] == [FOUND, FOUND]
    assert all(NUMS_FLAG not in r.flags for r in clear.rows)

    middle = read(_two_drugs(30), matcher(), CODES, today=TODAY)  # 이름 줄과 이름 줄의 한가운데
    assert [r.decision.status for r in middle.rows] == [AMBIGUOUS, AMBIGUOUS]
    assert all(NUMS_FLAG in r.flags for r in middle.rows)  # 어느 약의 숫자인지 확실하지 않으니 사용자가 확인한다
