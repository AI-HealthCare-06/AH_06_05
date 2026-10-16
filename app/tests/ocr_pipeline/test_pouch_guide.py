"""약봉투 카드의 복약 안내 읽기 (pouch_guide). 실제 p1 · p3 카드의 모양(안내 열 x 358~, 글자 높이 17~20, 표시 사이 15px)을 본뜬 합성 데이터"""

from app.services.ocr.pouch import parse_pouch
from app.tests.ocr_pipeline.test_pouch import data, fld, head


def w(text: str, x: float, y: float, width: float, conf: float = 0.99) -> dict:
    f = fld(text, x, y, width, 18)
    f["inferConfidence"] = conf
    return f


def card(y: float, name: str, *guide: dict) -> list[dict]:
    """이름(높이 24) · 성분(17) 줄은 왼쪽 열, 숫자는 카드 가운데, 안내는 x 358 이후의 열"""
    nums = [fld(v, x, y + 12, 10, 15) for x, v in zip((806, 850, 885), ("1", "3", "5"), strict=True)]
    return [fld(name, 136, y, 200, 24), fld("아세트아미노펜500mg", 134, y + 40, 160, 17), *nums, *guide]


def guides(*cards: list[dict]) -> list[list[str]]:
    t = parse_pouch(data(head() + [f for c in cards for f in c]))
    assert t is not None
    return [r.guide for r in t.rows]


def test_chips_sentences_and_wrapped_sentence():
    c = card(
        200,
        "슈가메트서방정",
        w("쪼개지", 363, 205, 47), w("마세요", 411, 205, 45), w("씹지", 471, 205, 32), w("마세요", 505, 205, 46),  # 표시 둘
        w("식사와", 358, 230, 45), w("함께", 405, 230, 30), w("복용하세요.", 437, 230, 75), w("저혈당", 515, 230, 45),  # 문장 + 이어지는 문장
        w("증세가", 358, 252, 45), w("나타나면", 405, 252, 55), w("상의하세요.", 463, 252, 75),
    )  # fmt: skip
    assert guides(c) == [
        ["쪼개지 마세요", "씹지 마세요", "식사와 함께 복용하세요.", "저혈당 증세가 나타나면 상의하세요."]
    ]


def test_first_short_line_is_a_tag_but_a_short_sentence_is_text():
    tag = card(
        200,
        "소론도정",
        w("위장장애", 430, 205, 58),
        w("주의", 491, 205, 30),
        w("식후에", 430, 230, 40),
        w("드세요.", 472, 230, 50),
    )
    sentence = card(200, "소론도정", w("물과", 430, 205, 30), w("드세요.", 462, 205, 50))
    assert guides(tag) == [["위장장애 주의", "식후에 드세요."]]
    assert guides(sentence) == [["물과 드세요."]]


def test_nouns_ending_in_yo_or_da_do_not_end_a_sentence():
    c = card(
        200,
        "아스피린",
        w("알리세요.", 358, 205, 60), w("코피,", 421, 205, 30), w("생리과다", 453, 205, 55),  # "생리과다" 끝의 다
        w("지속되면", 358, 230, 55), w("상의하세요", 415, 230, 70),  # 마침표 없는 끝맺음
    )  # fmt: skip
    assert guides(c) == [["알리세요.", "코피, 생리과다 지속되면 상의하세요"]]
    d = card(200, "약", w("필요", 358, 205, 30), w("시", 391, 205, 10), w("복용하세요.", 403, 205, 75))
    assert guides(d) == [["필요 시 복용하세요."]]


def test_unfinished_text_and_unsure_letters_are_not_kept():
    c = card(
        200,
        "약이름정",
        w("정상", 358, 205, 30), w("문장", 390, 205, 30), w("입니다.", 422, 205, 50),
        w("흐린", 358, 230, 30, 0.5), w("글자", 390, 230, 30, 0.99), w("있어요.", 422, 230, 50, 0.99),  # 한 낱말이 0.6 미만
        w("평균이", 358, 255, 45, 0.7), w("낮은", 406, 255, 30, 0.7), w("문장이에요.", 438, 255, 75, 0.9),  # 평균 0.77 < 0.8
        w("복용", 358, 280, 30), w("중에도", 390, 280, 40), w("계속해서", 432, 280, 55), w("꾸준히", 489, 280, 45), w("먹어야", 536, 280, 45),  # 끝맺음 없이 끝남(13자) → 버림
    )  # fmt: skip
    assert guides(c) == [["정상 문장 입니다."]]


def test_left_column_and_other_cards_do_not_leak_and_last_card_reads_to_table_end():
    one = card(200, "알마겔정", w("앞카드", 358, 225, 45), w("안내입니다.", 405, 225, 70))
    two = card(
        300,
        "소론도정",
        w("뒷카드", 358, 325, 45),
        w("안내입니다.", 405, 325, 70),
        w("추가", 358, 350, 30),
        w("안내입니다.", 391, 350, 70),
    )
    got = guides(one, two)
    assert got == [["앞카드 안내입니다."], ["뒷카드 안내입니다.", "추가 안내입니다."]]
    assert "아세트아미노펜500mg" not in sum(got, [])  # 성분 줄(왼쪽 열)은 안내가 아니다


def test_tiny_units_and_duplicates():
    dup = card(200, "중복정", w("주의", 358, 205, 25), w("같은표시", 440, 205, 60), w("같은표시", 520, 205, 60))
    assert guides(dup) == [["같은표시"]]  # 두 글자 조각은 버리고, 같은 표시는 한 번만


def test_receipt_strip_and_number_columns_are_never_read_as_guidance():
    from app.tests.ocr_pipeline.test_pouch import strip

    t = parse_pouch(data(head() + strip() + card(200, "알마겔정", w("안내입니다.", 358, 225, 70))))
    assert t is not None and t.rows[0].guide == ["안내입니다."]
    assert not any(any(x in g for x in ("홍길동", "영등포구")) for g in t.rows[0].guide)


def test_ingredient_line_split_in_two_words_is_not_guidance():
    c = [
        fld("노바스크정", 136, 200, 150, 24),
        fld("암로디핀", 134, 240, 80, 17), fld("베실산염", 216, 240, 60, 17), fld("정제형태", 275, 240, 40, 17),  # 성분 줄이 여러 낱말(간격 2px · 겹침 -3px)
        fld("[고혈압", 135, 262, 70, 17), fld("치료제]", 207, 262, 55, 17),
        *[fld(v, x, 212, 10, 15) for x, v in zip((806, 850, 885), ("1", "1", "30"), strict=True)],
        w("안내입니다.", 358, 245, 70),
    ]  # fmt: skip
    assert guides(c) == [["안내입니다."]]


def test_tag_above_the_name_center_belongs_to_its_own_card_not_the_previous_one():
    """p3: "위장장애 주의" 표시는 이름 줄 가운데보다 9px 위에 있다. 앞 카드의 마지막 안내와 섞이지 않는다"""
    one = card(200, "알마겔정", w("앞카드", 358, 235, 45), w("안내입니다.", 405, 235, 70))
    two = card(
        300, "소론도정", w("뒷카드", 430, 294, 45), w("주의표시", 490, 294, 60), w("뒷안내입니다.", 430, 322, 80)
    )
    assert guides(one, two) == [["앞카드 안내입니다."], ["뒷카드", "주의표시", "뒷안내입니다."]]


def test_fragment_before_a_chip_line_is_dropped_and_midline_short_fragment_is_text():
    c = card(
        200,
        "약이름정",
        w("복용", 358, 205, 30), w("중에도", 390, 205, 40), w("계속해서", 432, 205, 55), w("꾸준히", 489, 205, 45), w("먹어야", 536, 205, 45),  # 끝맺음 없음
        w("쪼개지", 363, 230, 47), w("마세요", 411, 230, 45), w("씹지", 471, 230, 32), w("마세요", 505, 230, 46),  # 표시 줄
        w("하루", 358, 255, 30), w("세번", 390, 255, 30), w("복용하세요.", 422, 255, 75),
    )  # fmt: skip
    assert guides(c) == [["쪼개지 마세요", "씹지 마세요", "하루 세번 복용하세요."]]
    d = card(
        200,
        "약이름정",
        w("물과", 358, 205, 30), w("함께", 390, 205, 30), w("드세요.", 422, 205, 50), w("필요", 475, 205, 30),  # 맨 위 줄: 문장 + 끝 조각
        w("시", 358, 230, 10), w("복용하세요.", 372, 230, 75),
    )  # fmt: skip
    assert guides(d) == [["물과 함께 드세요.", "필요 시 복용하세요."]]


def test_long_segment_on_a_chip_line_is_text_and_cap_is_ten():
    c = card(
        200,
        "약이름정",
        w("간주의", 363, 205, 47), w("식후에", 440, 205, 45), w("꾸준히", 487, 205, 45), w("반드시", 534, 205, 45), w("복용하세요.", 581, 205, 75),
    )  # fmt: skip
    assert guides(c) == [["간주의", "식후에 꾸준히 반드시 복용하세요."]]
    chips = [w(f"표시{i:02d}번", 358 + 100 * (i % 4), 205 + 22 * (i // 4), 60) for i in range(12)]
    assert len(guides(card(200, "많은정", *chips))[0]) == 10


def test_words_on_one_line_may_be_slightly_misaligned_and_a_short_middle_word_is_text():
    c = card(
        200,
        "약이름정",
        w("물과", 358, 205, 30), w("함께", 390, 208, 30), w("드세요.", 422, 203, 50), w("필요", 475, 206, 30),  # 세로로 3px씩 어긋남
        w("시", 358, 230, 10),  # 짧고 끝맺음 없는 줄이 맨 위 줄이 아니면 표시가 아니다
        w("복용하세요.", 358, 252, 75),
    )  # fmt: skip
    assert guides(c) == [["물과 함께 드세요.", "필요 시 복용하세요."]]
