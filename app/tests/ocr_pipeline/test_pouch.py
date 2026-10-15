"""약봉투 표 읽기 시험 (DB · 네트워크 없음) — 실제 약봉투 사진 모양을 본떠 만든 합성 글자 위치로 확인 (10/15)

실제 사진(p1 · r2)의 CLOVA 결과는 개인정보가 있을 수 있어 저장소에 넣지 않았다. 아래 좌표는 p1(카드형)과 r2(한 줄형)에서
잰 모양(머리글 세 낱말이 한 줄, 숫자 칸 간격, 이름 글자가 성분 · 안내 줄보다 큼, 오른쪽 영수증 띠)을 줄인 것이다.
"""

import random
from datetime import date

from app.services.ocr.matcher import NameMatcher
from app.services.ocr.pipeline import read
from app.services.ocr.pouch import dispensed_date, parse_pouch

TODAY = date(2026, 10, 15)


def fld(text: str, x: float, y: float, w: float, h: float) -> dict:
    return {
        "inferText": text,
        "inferConfidence": 0.99,
        "boundingPoly": {
            "vertices": [{"x": x, "y": y}, {"x": x + w, "y": y}, {"x": x + w, "y": y + h}, {"x": x, "y": y + h}]
        },
    }


def data(fields: list[dict]) -> dict:
    return {"images": [{"fields": fields}]}


def head(y: float = 160) -> list[dict]:
    return [fld("투약량", 788, y, 43, 18), fld("횟수", 840, y, 30, 18), fld("일수", 876, y, 29, 16)]


def strip() -> list[dict]:
    """오른쪽 영수증 띠: 환자 이름 · 주소 · 전화 · 숫자 (일수 칸보다 오른쪽)"""
    return [
        fld("환자", 1000, 120, 40, 17), fld("홍길동", 1050, 120, 60, 17),
        fld("서울시", 1000, 200, 60, 17), fld("영등포구", 1065, 200, 80, 17),
        fld("01012345678", 1101, 331, 125, 20), fld("88", 1235, 415, 23, 16), fld("4", 1098, 795, 20, 25),
    ]  # fmt: skip


def card(y: float, name: str, nums: tuple[str, str, str] | None = ("1", "3", "5")) -> list[dict]:
    """카드형 한 칸 (p1): 이름(굵음 높이 24) 아래에 성분 · 효능 · 복약 안내(작음 높이 17), 숫자는 카드 가운데"""
    out = [
        fld(name, 200, y, 220, 24),
        fld("아세트아미노펜", 200, y + 28, 120, 17),
        fld("해열 · 진통제", 200, y + 48, 100, 17),
        fld("식후 30분에 복용하세요", 200, y + 68, 200, 17),
    ]
    if nums:
        for x, v in zip((806, 850, 885), nums, strict=True):
            out.append(fld(v, x, y + 40, 10, 15))
    return out


def card_table(*cards: list[dict]) -> list[dict]:
    return [f for c in cards for f in c]


def rows_of(d: dict) -> list[tuple[str, list]]:
    t = parse_pouch(d)
    assert t is not None
    return [(r.name, r.nums) for r in t.rows]


def test_card_style_rows_names_and_columns():
    d = data(
        head()
        + strip()
        + card_table(
            card(200, "알마겔정"),
            card(300, "슈가메트서방정5/100···", ("1", "2", "30")),
            card(400, "*리피토정10mg", ("2", "1", "7")),
        )
    )
    t = parse_pouch(d)
    assert t is not None and t.n_anchor == 3 and t.disease_raw is None
    assert [(r.name, r.nums) for r in t.rows] == [
        ("알마겔정", [1.0, 3.0, 5.0]),
        ("슈가메트서방정5/100", [1.0, 2.0, 30.0]),  # 끝의 잘림 표시 "···" 제거
        ("리피토정10mg", [2.0, 1.0, 7.0]),  # 앞의 "*" 제거
    ]  # 성분 · 효능 · 복약 안내 줄은 약이 되지 않고, 영수증 띠(이름 · 주소 · 전화번호 · 숫자)는 읽지 않는다


def test_field_order_does_not_matter():
    fields = head() + strip() + card_table(card(200, "알마겔정"), card(300, "소론도정", ("1", "1", "3")))
    want = rows_of(data(fields))
    for seed in range(5):
        random.Random(seed).shuffle(fields)
        assert rows_of(data(fields)) == want  # CLOVA는 글자 목록 순서를 보장하지 않는다


def test_one_line_style_every_line_is_a_drug():
    fields = head(200)
    for i, (name, nums) in enumerate(
        [("위더스세파클러캡슐250mg", "133"), ("세토펜8시간이알서방정", "133"), ("레마이드정", "133")]
    ):
        y = 230 + 26 * i
        fields.append(fld("*" + name, 40, y, 260, 18))
        for x, v in zip((806, 850, 885), nums, strict=True):
            fields.append(fld(v, x, y, 10, 16))
    fields += [fld("복용방법", 40, 120, 80, 18)]  # 머리글 위쪽 글자는 보지 않는다
    assert rows_of(data(fields)) == [
        ("위더스세파클러캡슐250mg", [1.0, 3.0, 3.0]),
        ("세토펜8시간이알서방정", [1.0, 3.0, 3.0]),
        ("레마이드정", [1.0, 3.0, 3.0]),
    ]


def test_lines_without_numbers_at_the_edges_are_dropped_but_inner_ones_kept():
    d = data(
        head()
        + card_table(
            card(200, "안내문구글자", None),  # 처음: 표 바깥 글자
            card(300, "알마겔정"),
            card(400, "숫자못읽은약", None),  # 가운데: 약일 수 있어서 남김
            card(500, "소론도정", ("1", "1", "3")),
            card(600, "방문일안내글자", None),  # 끝: 표 바깥 글자
        )
    )
    t = parse_pouch(d)
    assert t is not None
    assert [r.name for r in t.rows] == ["알마겔정", "숫자못읽은약", "소론도정"]
    assert t.rows[1].nums == [None, None, None]


def test_no_header_or_no_numbers_or_misread_header_returns_none():
    assert parse_pouch(data(card_table(card(200, "알마겔정")))) is None  # 머리글 없음
    assert parse_pouch(data(head() + card_table(card(200, "알마겔정", None)))) is None  # 숫자 없음
    broken = [fld("투약량", 788, 160, 43, 18), fld("횟수", 840, 160, 30, 18), fld("밀수", 876, 160, 29, 16)]
    assert (
        parse_pouch(data(broken + card_table(card(200, "알마겔정")))) is None
    )  # p2처럼 "일수"를 잘못 읽음 → 지원 안 함
    spread = [fld("투약량", 788, 160, 43, 18), fld("횟수", 840, 260, 30, 18), fld("일수", 876, 360, 29, 16)]
    assert parse_pouch(data(spread + card_table(card(200, "알마겔정")))) is None  # 같은 줄이 아니면 머리글이 아니다


def test_read_marks_pill_bag_and_does_not_leak_receipt_into_meta():
    matcher = NameMatcher([("1", "알마겔정")])
    fields = (
        head()
        + strip()
        + card_table(card(200, "알마겔정"))
        + [fld("조제일", 100, 40, 50, 17), fld("2026-10-12", 155, 40, 90, 17)]
        + [fld("승인일", 1000, 300, 50, 17), fld("2026-09-01", 1055, 300, 90, 17), fld("○○병원", 1000, 330, 60, 17)]
    )
    res = read(data(fields), matcher, {}, today=TODAY)
    assert (res.status, res.doc_type) == ("ok", "pill_bag")
    assert res.issued == date(2026, 10, 12)  # 조제일만 읽는다 (영수증 띠의 승인일은 읽지 않는다)
    assert res.hospital_name is None and res.timing is None and res.birth is None
    assert [(r.read_name, r.dose, r.times, r.days) for r in res.rows] == [("알마겔정", 1.0, 3.0, 5.0)]
    assert "홍길동" not in " ".join(r.read_name for r in res.rows)


def test_prescription_still_reads_as_prescription():
    from app.tests.ocr_pipeline.test_pipeline import SAMPLE, matcher

    res = read(SAMPLE, matcher(), {}, today=TODAY)
    assert (res.status, res.doc_type) == ("ok", "prescription")


def test_dispensed_date_rules():
    def f(*pairs: tuple[str, str]) -> list[dict]:
        return [fld(t, 10 + 100 * i, 10, 90, 17) for i, p in enumerate(pairs) for t in p]

    assert dispensed_date(f(("조제일", "2026-10-12")), TODAY) == (date(2026, 10, 12), [])
    assert dispensed_date(f(("조제일자:", "2026.10.12"), ("조제일", "2026/10/12")), TODAY)[0] == date(2026, 10, 12)
    d, flags = dispensed_date(f(("조제일", "2026-10-12"), ("조제일", "2026-10-13")), TODAY)
    assert d is None and flags == ["조제일이 서로 다르게 적혀 있음"]
    d, flags = dispensed_date(f(("발행일", "2026-10-12"), ("승인일", "2026-09-01")), TODAY)
    assert d is None and flags == ["조제일 못 읽음"]  # 라벨이 조제일이 아니면 쓰지 않는다
    assert dispensed_date(f(("조제일", "2027-01-01")), TODAY)[0] is None  # 미래 날짜
    assert dispensed_date(f(("조제일", "2026-02-31")), TODAY)[0] is None  # 달력에 없는 날짜


def test_card_name_height_cut_survives_narrow_gap_and_tall_side_text():
    """실제 p1: 이름 23~29, 분류 · 성분 · 안내 15~21로 겹침이 좁다. 이름만큼 큰 "[분류]" 줄, 이름 줄 오른쪽에 떨어진 큰 글자, 오른쪽의 큰 안내 줄은 이름이 아니다"""

    def one(y: float, name: str, h: float) -> list[dict]:
        return (
            [
                fld(name, 136, y, 160, h),
                fld("[항혈전제]", 136, y + 28, 90, 24),
                fld("메트포르민염산염", 135, y + 46, 150, 17),
            ]
            + [
                fld("전문가와", 358, y + 2, 70, 24),
                fld("상의하세요", 440, y + 2, 80, 24),
                fld("식사와", 358, y + 60, 50, 24),
            ]
            + [fld(v, x, y + 25, 10, 15) for x, v in zip((806, 850, 885), ("1", "2", "7"), strict=True)]
        )

    d = data(head() + one(200, "알마겔정", 23) + one(300, "리피토정10mg", 29) + one(400, "소론도정", 23))
    assert rows_of(d) == [
        ("알마겔정", [1.0, 2.0, 7.0]),
        ("리피토정10mg", [1.0, 2.0, 7.0]),
        ("소론도정", [1.0, 2.0, 7.0]),
    ]


def test_one_line_style_keeps_attached_strength_token_and_ignores_tall_top_line():
    fields = [fld("투약량", 206, 489, 44, 15), fld("횟수", 244, 489, 22, 15), fld("일수", 266, 489, 25, 15)] + [
        fld("(최근내방일:", 23, 501, 98, 21), fld("2024-05-02)", 116, 502, 100, 20),
        fld("*레마이드정", 23, 569, 73, 19), fld("100mg", 99, 569, 41, 19),
    ]  # fmt: skip
    for x, v in zip((213, 244, 264), ("1", "3", "3"), strict=True):
        fields.append(fld(v, x, 571, 10, 13))
    assert rows_of(data(fields)) == [("레마이드정100mg", [1.0, 3.0, 3.0])]  # 숫자 없는 맨 위 줄은 버린다


def test_truncated_name_is_never_auto_confirmed_even_when_one_product_matches():
    """카드가 긴 이름을 "···"로 줄이면 함량 등 뒷부분이 없다. 마스터에서 한 약과만 글자가 맞아도 (실제 p1: 슈가메트서방정5/100··· → 5/1000) 사용자가 고르게 한다"""
    from app.services.ocr.matcher import AMBIGUOUS, FOUND
    from app.services.ocr.pipeline import CUT_FLAG

    matcher = NameMatcher([("1", "슈가메트서방정5/1000밀리그램_(1정)"), ("2", "알마겔정")])
    d = data(head() + card_table(card(200, "슈가메트서방정5/100···"), card(300, "알마겔정")))
    t = parse_pouch(d)
    assert t is not None and [r.cut for r in t.rows] == [True, False]
    res = read(d, matcher, {}, today=TODAY)
    cut_row, whole_row = res.rows
    assert cut_row.decision.status == AMBIGUOUS and cut_row.decision.candidates[0].edi_code == "1"
    assert CUT_FLAG in cut_row.flags
    assert whole_row.decision.status == FOUND and CUT_FLAG not in whole_row.flags


def _rotated(fields: list[dict], deg: float) -> list[dict]:
    import copy
    import math

    out = copy.deepcopy(fields)
    a = math.radians(deg)
    for f in out:
        for v in f["boundingPoly"]["vertices"]:
            x, y = v["x"], v["y"]
            v["x"], v["y"] = x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a)
    return out


def test_tilted_pill_bag_photo_is_read_like_a_straight_one():
    """실제 p1은 1~3도만 기울어도 (기울기 보정 없이는) 줄이 깨졌다. 처방전과 같은 기울기 보정을 거쳐 읽는다"""
    matcher = NameMatcher([("1", "알마겔정")])
    fields = (
        head()
        + strip()
        + card_table(card(200, "알마겔정"), card(300, "소론도정", ("1", "1", "3")), card(400, "리피토정10mg"))
    )
    want = [(r.read_name, r.dose, r.times, r.days) for r in read(data(fields), matcher, {}, today=TODAY).rows]
    assert len(want) == 3
    for deg in (-5, -2, 1, 3, 8):
        res = read(data(_rotated(fields, deg)), matcher, {}, today=TODAY)
        assert (res.status, res.doc_type) == ("ok", "pill_bag")
        assert [(r.read_name, r.dose, r.times, r.days) for r in res.rows] == want, deg


def test_lost_name_line_makes_row_count_mismatch_visible():
    """이름이 작게 읽혀 약 줄이 사라져도 그 약의 숫자는 남아 있으므로 "줄 수가 맞지 않아요"로 사용자에게 알린다"""
    matcher = NameMatcher([("1", "알마겔정")])
    first = card(200, "알마겔정")
    first[0] = fld("알마겔정", 200, 200, 220, 17)  # 이름 글자가 성분 줄만큼 작게 읽힌 경우
    d = data(head() + card_table(first, card(300, "소론도정", ("1", "1", "3")), card(400, "리피토정10mg")))
    res = read(d, matcher, {}, today=TODAY)
    assert len(res.rows) == 2 and res.row_count_mismatch
