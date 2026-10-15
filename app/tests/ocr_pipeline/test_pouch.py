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
        words = [t for p in pairs for t in p]
        return [fld(t, 10 + 100 * i, 10, 90, 17) for i, t in enumerate(words)]

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
        fld("최근내방일:", 23, 501, 98, 21), fld("2024-05-02", 116, 502, 100, 20),
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


def test_card_with_unreadable_text_still_counts_its_numbers_so_mismatch_is_visible():
    """이름 · 성분 글자를 모두 못 읽은 카드는 약 줄이 되지 못하지만 숫자는 남으므로 "줄 수가 맞지 않아요"로 사용자에게 알린다"""
    matcher = NameMatcher([("1", "알마겔정")])
    blank = [fld(v, x, 340, 10, 15) for x, v in zip((806, 850, 885), ("1", "1", "3"), strict=True)]
    d = data(head() + card_table(card(200, "알마겔정"), blank, card(400, "리피토정10mg")))
    res = read(d, matcher, {}, today=TODAY)
    assert [r.read_name for r in res.rows] == ["알마겔정", "리피토정10mg"] and res.row_count_mismatch


def test_p3_shape_extra_position_column_pill_image_text_and_big_ad_below():
    """실제 p3(팜플약국): 머리글에 "위치"가 한 칸 더 있고, 약 사진 안의 글자(SW · 10)가 이름 왼쪽에 있고, 이름(19~22)과 성분(16~18)의 글자 높이 차이가 1px로 작고,
    표 아래에 큰 광고 글자(높이 36~47)가 있다"""
    fields = [
        fld("위치", 851, 171, 32, 19), fld("투약량", 905, 171, 49, 19), fld("횟수", 971, 171, 34, 19), fld("일수", 1025, 171, 33, 19),
    ]  # fmt: skip
    drugs = [("에스로반정", "에스오메프라줄", ("1", "1", "10")), ("뮤코펙트정", "암브록솔염산염", ("2", "3", "5")),
             ("로라탐정", "로라타딘", ("1", "1", "10"))]  # fmt: skip
    for i, (name, ingredient, (dose, times, days)) in enumerate(drugs):
        y = 225 + 97 * i
        fields += [
            fld("SW", 82, y + 13, 43, 23),  # 약 사진 안의 글자
            fld(name, 184, y, 85, 19 + (i % 2) * 3), fld("20mg", 270, y, 55, 22),
            fld(ingredient, 184, y + 28, 90, 18), fld("[위장장애", 434, y - 7, 55, 18),
            fld("1", 861, y - 1, 10, 14), fld(dose, 922, y - 1, 12, 14), fld(times, 985, y - 1, 10, 14), fld(days, 1030, y - 1, 22, 14),
        ]  # fmt: skip
    fields += [fld("지금,", 92, 796, 80, 36), fld("건강관리", 94, 842, 180, 47), fld("시작하세요!", 279, 842, 200, 47)]
    assert rows_of(data(fields)) == [
        ("에스로반정20mg", [1.0, 1.0, 10.0]),
        ("뮤코펙트정20mg", [2.0, 3.0, 5.0]),
        ("로라탐정20mg", [1.0, 1.0, 10.0]),
    ]  # "위치" 칸 숫자(1)는 읽지 않고, 광고 문구는 약이 되지 않는다


def test_small_guidance_text_on_the_name_row_is_not_glued_to_the_name():
    """실제 p1: 이름("슈가메트서방정5/100···", 높이 24) 바로 오른쪽 같은 줄에 안내 문장(높이 17~18)이 시작한다. 이름 뒤 "100mg"(같은 크기)와 달리 붙이지 않는다"""
    d = data(head() + [fld("슈가메트서방정5/100···", 136, 286, 200, 24), fld("쪼개지", 363, 295, 45, 18), fld("마세요", 411, 295, 45, 18)]
             + [fld(v, x, 290, 10, 15) for x, v in zip((806, 850, 885), ("1", "6", "3"), strict=True)])  # fmt: skip
    assert rows_of(d) == [("슈가메트서방정5/100", [1.0, 6.0, 3.0])]


def test_pill_image_text_on_the_name_row_and_parenthesized_note_are_not_names():
    """약 사진 안의 글자("10", "TY")가 이름과 같은 줄에 걸려도 이름이 사라지지 않는다. "(최근내방일 …)"처럼 괄호로 시작하는 줄은 글자가 커도 이름이 아니다"""
    cards = []
    for i, name in enumerate(["로라탐정", "타이레놀정"]):
        y = 200 + 100 * i
        cards += [fld("10", 80, y + 2, 22, 21), fld(name, 184, y, 85, 21), fld("성분줄", 184, y + 28, 70, 17)]
        cards += [fld(v, x, y + 5, 10, 14) for x, v in zip((806, 850, 885), ("1", "2", "3"), strict=True)]
    note = [fld("(최근내방일:2024-05-02)", 184, 276, 200, 26)]  # 두 카드 사이, 이름보다 큰 글자
    note += [
        fld("TY", 80, 244, 22, 21),
        fld("전문가와상의하세요", 400, 240, 200, 30),
    ]  # 약 사진 글자와 같은 줄의 오른쪽 안내 문장(큼)
    assert rows_of(data(head() + cards + note)) == [("로라탐정", [1.0, 2.0, 3.0]), ("타이레놀정", [1.0, 2.0, 3.0])]


def test_name_join_rules_size_truncation_marker_and_slightly_overlapping_boxes():
    nums = [fld(v, x, 290, 10, 15) for x, v in zip((806, 850, 885), ("1", "6", "3"), strict=True)]
    # 이름 바로 옆에 붙은 작은 글자(안내 문장, 간격 4px)는 크기가 작아서 붙이지 않는다
    small = [fld("알마겔정", 136, 286, 100, 24), fld("쪼개지", 240, 295, 45, 15)]
    assert rows_of(data(head() + small + nums)) == [("알마겔정", [1.0, 6.0, 3.0])]
    # "···"로 끝난 이름 뒤에는 같은 크기의 글자가 바로 옆에 있어도 붙이지 않는다
    cut = [fld("슈가메트서방정5/100···", 136, 286, 200, 24), fld("20mg", 338, 286, 40, 24)]
    assert rows_of(data(head() + cut + nums)) == [("슈가메트서방정5/100", [1.0, 6.0, 3.0])]
    # 상자가 살짝 겹쳐 있어도(간격 -2px) 이름 뒤 함량은 붙는다
    touching = [fld("리피토정", 136, 286, 100, 24), fld("10mg", 234, 286, 40, 24)]
    assert rows_of(data(head() + touching + nums)) == [("리피토정10mg", [1.0, 6.0, 3.0])]


def test_dispensed_date_label_split_into_letters_and_other_rows_in_between():
    """실제 p3: "조 제 일" 글자가 낱낱이 나뉘고, 낱말 순서 중간에 다른 줄(전표 번호)이 끼어 있다"""
    fields = [
        fld("조", 1127, 129, 30, 17),
        fld("제", 1162, 129, 30, 17),
        fld("일", 1200, 129, 30, 17),
        fld("20250602-002", 1274, 74, 120, 17),
        fld("2025.06.02", 1274, 129, 100, 17),
        fld("2025.05.15", 1359, 958, 100, 17),  # 라벨 없는 다른 날짜
    ]
    assert dispensed_date(fields, TODAY) == (date(2025, 6, 2), [])
    # 날짜가 다른 줄에 있으면 라벨과 잇지 않는다
    far = [fld("조제일", 100, 10, 90, 17), fld("2025.06.02", 100, 60, 100, 17)]
    assert dispensed_date(far, TODAY)[0] is None


def test_dispensed_date_same_line_tolerates_small_vertical_offset():
    fields = [fld("조제일", 100, 10, 90, 17), fld("2025.06.02", 220, 13, 100, 17)]  # 3px 어긋남
    assert dispensed_date(fields, TODAY) == (date(2025, 6, 2), [])


def test_dispensed_date_between_two_stacked_labels_is_not_taken():
    """실제 r2: "조제일자:"(위)와 "복용완료일"(아래) 두 줄 사이에 날짜가 끼어 있다. 어느 쪽 날짜인지 알 수 없으니 읽지 않는다"""
    fields = [
        fld("조제일자:", 954, 116, 110, 23),
        fld("복용완료일", 954, 146, 95, 23),
        fld("2024-05-04", 1060, 136, 122, 22),
    ]
    assert dispensed_date(fields, TODAY) == (None, ["조제일 못 읽음"])
    # 글자 높이의 0.3배를 넘게 어긋난 날짜는 같은 줄이 아니다 (17px 글자, 8px 어긋남)
    off = [fld("조제일", 100, 10, 90, 17), fld("2025.06.02", 220, 18, 100, 17)]
    assert dispensed_date(off, TODAY)[0] is None


def _list_table(names=("씨프로바이정250밀리그램", "화록소정", "*라니드정", "*부스코판당의정"), y0=368, pitch=17):
    """실제 p4_2016: 머리글 없는 "이름 + 숫자 3개" 목록 (숫자 칸 x 600 · 628 · 659, 줄 간격 17)"""
    out = []
    for i, n in enumerate(names):
        y = y0 + i * pitch
        out += [fld(n, 493, y, 85, 12)] + [fld(v, x, y, 8, 11) for x, v in zip((600, 628, 659), "122", strict=True)]
    return out


def _receipt_above() -> list[dict]:
    return [
        fld("투약일수", 623, 36, 37, 12), fld("2", 660, 40, 8, 9),  # 영수증 윗줄의 같은 x 숫자
        fld("약제비총액", 491, 79, 51, 13), fld("본인부담금", 492, 93, 50, 13),
    ]  # fmt: skip


def test_headerless_list_is_read_in_order_and_marked_headerless():
    below = [fld("조제약은", 95, 449, 33, 11), fld("2", 660, 520, 8, 11), fld("1", 600, 560, 8, 11)]
    t = parse_pouch(data(_receipt_above() + _list_table() + below))
    assert t is not None and t.headerless
    assert [(r.name, r.nums) for r in t.rows] == [
        ("씨프로바이정250밀리그램", [1.0, 2.0, 2.0]),
        ("화록소정", [1.0, 2.0, 2.0]),
        ("라니드정", [1.0, 2.0, 2.0]),
        ("부스코판당의정", [1.0, 2.0, 2.0]),
    ]
    assert t.n_anchor == 4  # 표 위 · 아래의 같은 칸 숫자는 세지 않는다


def test_headerless_list_keeps_unread_number_empty_not_shifted():
    f = [x for x in _list_table() if not (x["inferText"] == "1" and x["boundingPoly"]["vertices"][0]["y"] == 402)]
    t = parse_pouch(data(f))
    assert t is not None
    assert [r.nums for r in t.rows][2] == [None, 2.0, 2.0]


def test_headerless_needs_two_aligned_rows_names_and_no_prescription_form():
    one = parse_pouch(data(_list_table(names=("화록소정",))))
    assert one is None  # 한 줄만으로는 표인지 알 수 없다
    nameless = [x for x in _list_table() if not x["inferText"].startswith(("씨", "화", "*"))]
    assert parse_pouch(data(nameless)) is None  # 이름 없는 숫자 줄
    uneven = [fld(n, 493, y, 85, 12) for n, y in (("화록소정", 368), ("라니드정", 380), ("부스코판당의정", 440))] + [
        fld(v, x, y, 8, 11) for y in (368, 380, 440) for x in (600, 628, 659) for v in "1"
    ]
    assert parse_pouch(data(uneven)) is None  # 줄 간격이 고르지 않으면 표가 아니다 (두 줄 이상 이어지지 않음)
    rx = [fld("질병분류기호", 100, 20, 80, 14)]
    assert parse_pouch(data(rx + _list_table())) is None  # 머리글이 지워진 처방전은 약봉투로 읽지 않는다


def test_headerless_list_read_flags_every_row_and_document():
    d = data(_receipt_above() + _list_table())
    r = read(d, NameMatcher([("1", "화록소정")]), {}, today=TODAY)
    assert r.status == "ok" and r.doc_type == "pill_bag"
    assert any("머리글이 없어" in f for f in r.meta_flags)
    assert all(any("머리글이 없어" in f for f in x.flags) for x in r.rows)
    # 머리글이 있는 표에는 이 표시가 붙지 않는다
    r2 = read(data(head() + card_table(card(200, "알마겔정"))), NameMatcher([("1", "알마겔정")]), {}, today=TODAY)
    assert not any("머리글이 없어" in f for f in r2.meta_flags + r2.rows[0].flags)


def test_headerless_two_row_list_with_stray_number_between_columns():
    """줄이 두 개뿐이어도 읽고(칸마다 숫자 2개), 칸 사이에 떨어진 숫자 하나가 칸으로 오인되지 않는다"""
    t = parse_pouch(data(_list_table(names=("화록소정", "라니드정")) + [fld("7", 614, 330, 8, 11)]))
    assert t is not None and [(r.name, r.nums) for r in t.rows][0] == ("화록소정", [1.0, 2.0, 2.0])


def test_headerless_rejects_lookalikes():
    def grid(ys, xs, text="9"):
        return [fld(text, x, y, 8, 11) for y in ys for x in xs]

    # 이름이 두 글자뿐인 줄("합계" 등)은 약 이름이 아니다
    two = [fld(n, 493, 368 + 17 * i, 30, 12) for i, n in enumerate(("합계", "소계", "총액"))]
    assert parse_pouch(data(two + grid((368, 385, 402), (600, 628, 659)))) is None
    # 숫자가 줄마다 한 칸에만 있으면 표가 아니다
    one_col = [
        x
        for x in _list_table()
        if x["boundingPoly"]["vertices"][0]["x"] != 628
        and x["boundingPoly"]["vertices"][0]["x"] != 659
        or not x["inferText"].isdigit()
    ]
    assert parse_pouch(data(one_col)) is None
    # 이름이 숫자 줄과 한 줄 가까이 떨어져 있으면(위 · 아래 줄의 글자) 그 줄의 이름이 아니다
    far = [fld(n, 493, 368 + 17 * i - 30, 85, 12) for i, n in enumerate(("화록소정", "라니드정", "부스코판당의정"))]
    assert parse_pouch(data(far + grid((368, 385, 402), (600, 628, 659), "1"))) is None
    # 세 칸이 너무 멀리 떨어져 있으면(글자 높이의 15배 넘게) 한 표의 칸이 아니다
    wide = [fld(n, 20, 368 + 17 * i, 85, 12) for i, n in enumerate(("화록소정", "라니드정"))]
    assert parse_pouch(data(wide + grid((368, 385), (600, 900, 1200), "1"))) is None


def test_headerless_picks_the_table_with_names_over_a_bigger_number_grid():
    """이름 없는 숫자 격자(금액표 등)가 줄이 더 많아도, 이름이 붙은 목록을 표로 읽는다"""
    grid = [fld("9", x, 40 + 17 * i, 8, 11) for i in range(6) for x in (100, 130, 160)]
    t = parse_pouch(data(grid + _list_table()))
    assert t is not None and t.rows[0].name == "씨프로바이정250밀리그램"


def test_headerless_rejects_one_number_per_row_columns_too_close_and_names_on_the_right():
    names = ("화록소정", "라니드정", "부스코판당의정", "알마겔정", "리피토정", "가나다정")
    # 줄마다 숫자가 한 칸에만 있다 (칸마다 두 번 나오지만 한 줄에 둘 이상 없다)
    stair = [fld(n, 493, 368 + 17 * i, 85, 12) for i, n in enumerate(names)]
    stair += [fld("1", (600, 628, 659)[i % 3], 368 + 17 * i, 8, 11) for i in range(6)]
    assert parse_pouch(data(stair)) is None
    # 세 칸이 글자 높이(11)의 1.2배(13.2)보다 가까우면 한 칸씩 나뉜 칸이 아니다
    close = [fld(n, 493, 368 + 17 * i, 85, 12) for i, n in enumerate(names[:3])]
    close += [fld("1", x, 368 + 17 * i, 8, 11) for i in range(3) for x in (600, 612, 624)]
    assert parse_pouch(data(close)) is None
    # 이름이 숫자 칸 오른쪽에 있으면 이름 칸이 아니다
    right = [fld(n, 700, 368 + 17 * i, 85, 12) for i, n in enumerate(names[:3])]
    right += [fld("1", x, 368 + 17 * i, 8, 11) for i in range(3) for x in (600, 628, 659)]
    assert parse_pouch(data(right)) is None


def _plain(y: float, name: str, name_h: float, sub: str, sub_h: float, nums=("1", "3", "5")) -> list[dict]:
    """카드 한 칸: 이름 줄 아래 성분 줄. 글자 크기를 마음대로 정한다 (숫자는 두 줄 사이)"""
    out = [fld(name, 200, y, 200, name_h), fld(sub, 200, y + 28, 200, sub_h)]
    out += [fld(v, x, y + 20, 10, 15) for x, v in zip((806, 850, 885), nums, strict=True)]
    return out


def test_name_is_the_top_line_even_when_the_ingredient_line_looks_taller():
    """흔들린 사진에서는 이름(20)보다 성분 줄(21)이 커 보일 수 있다. 크기가 아니라 구간 맨 위 줄이 이름이다 (p3 뮤코펙트정 19 / 암브록솔염산염 18 근처)"""
    d = data(
        head()
        + _plain(200, "알마겔정", 24, "알마게이트500mg", 17)
        + _plain(300, "뮤코펙트정", 20, "암브록솔염산염30mg", 21)
        + _plain(400, "소론도정", 24, "프레드니솔론5mg", 17)
    )
    t = parse_pouch(d)
    assert t is not None and [r.name for r in t.rows] == ["알마겔정", "뮤코펙트정", "소론도정"]
    assert not any(r.unsure for r in t.rows)


def test_tiny_top_line_falls_back_to_big_line_and_marks_row_unsure():
    """구간 맨 위에 유독 작은 줄(앞 카드 안내 꼬리)이 있으면 큰 글자 줄을 이름으로 하되, 글자 크기로 고른 것이라 사용자가 확인한다"""
    d = data(
        head()
        + _plain(200, "알마겔정", 24, "알마게이트500mg", 17)
        + [fld("식후에복용하세요", 200, 276, 150, 12)]  # 둘째 구간 맨 위의 작은 꼬리
        + _plain(300, "소론도정", 24, "프레드니솔론5mg", 17)
        + _plain(400, "리피토정", 24, "아토르바스타틴", 17)
    )
    t = parse_pouch(d)
    assert t is not None and [(r.name, r.unsure) for r in t.rows] == [
        ("알마겔정", False),
        ("소론도정", True),
        ("리피토정", False),
    ]
    r = read(d, NameMatcher([("1", "소론도정")]), {}, today=TODAY)
    row = r.rows[1]
    assert row.decision.status == "ambiguous" and any(
        "확실하지" in f for f in row.flags
    )  # 약 마스터에 있어도 자동 확정하지 않는다


def test_big_line_right_under_a_name_is_not_a_second_drug():
    """이름 바로 아래 "[분류]" 줄이 흔들려 이름만큼 커 보여도 약 줄이 아니다 (숫자가 그 줄로 가는 조용한 오류)"""
    d = data(
        head()
        + card_table(card(200, "알마겔정"), card(300, "소론도정"), card(400, "리피토정"))
        + [fld("관련질환용치료제", 200, 232, 150, 24)]
    )
    assert [n for n, _ in rows_of(d)] == ["알마겔정", "소론도정", "리피토정"]
    # 숫자 없는 약이 카드 간격만큼 떨어져 있으면 그대로 약으로 남는다 (기존 동작)
    far = data(head() + card_table(card(200, "알마겔정"), card(300, "숫자못읽은약", None), card(400, "리피토정")))
    assert [n for n, _ in rows_of(far)] == ["알마겔정", "숫자못읽은약", "리피토정"]


def test_strength_piece_joins_even_when_small_or_shifted_but_guidance_does_not():
    base = _plain(200, "로라탐정", 24, "로라타딘10mg", 17) + _plain(300, "소론도정", 24, "프레드니솔론5mg", 17)
    near = fld("10mg", 402, 206, 40, 11)  # 높이 11(이름의 0.46배) — 흔들려 작아진 함량 조각
    t = parse_pouch(data(head() + base + [near]))
    assert t is not None and t.rows[0].name == "로라탐정10mg"
    guide = fld("복용하세요", 402, 206, 60, 11)  # 같은 위치의 한글 안내 문장은 붙지 않는다
    t = parse_pouch(data(head() + base + [guide]))
    assert t is not None and t.rows[0].name == "로라탐정"


def test_number_in_dose_column_is_not_glued_to_the_name():
    """흔들려 투약량 숫자가 이름 칸 쪽으로 밀려도(칸 안의 숫자) 이름 뒤에 붙지 않는다"""
    d = data(
        head()
        + [fld("알마겔정", 640, 220, 140, 24), fld("1", 783, 224, 10, 15)]
        + [fld("3", 850, 224, 10, 15), fld("5", 885, 224, 10, 15)]
        + [
            fld("소론도정", 640, 320, 140, 24),
            fld("1", 783, 324, 10, 15),
            fld("3", 850, 324, 10, 15),
            fld("5", 885, 324, 10, 15),
        ]
    )
    t = parse_pouch(d)
    assert t is not None and [(r.name, r.nums) for r in t.rows] == [
        ("알마겔정", [1.0, 3.0, 5.0]),
        ("소론도정", [1.0, 3.0, 5.0]),
    ]


def test_strength_piece_that_is_tiny_or_on_another_line_is_not_joined():
    base = _plain(200, "로라탐정", 24, "로라타딘10mg", 17) + _plain(300, "소론도정", 24, "프레드니솔론5mg", 17)
    for piece in (
        fld("10mg", 402, 210, 40, 5),
        fld("10mg", 402, 222, 40, 11),
    ):  # 너무 작음(0.2배) · 거의 아래 줄(겹침 0.18)
        t = parse_pouch(data(head() + base + [piece]))
        assert t is not None and t.rows[0].name == "로라탐정"
