"""글자 위치로 이름 칸을 가리는 규칙 시험 (app/services/ocr/mask_layout.py) — DB · 네트워크 없음"""

import json
import random

from app.services.ocr import clova
from app.services.ocr.mask import mask
from app.services.ocr.mask_layout import join_masked, name_boxes
from app.services.ocr.pipeline import read
from app.tests.ocr_pipeline.test_pipeline import CODES, TODAY, matcher

H = 16


def box(text, x, y, w=None, h=H):
    w = w or h * len(text)
    return {"inferText": text, "inferConfidence": 0.99, "boundingPoly": {"vertices": [
        {"x": x, "y": y}, {"x": x + w, "y": y}, {"x": x + w, "y": y + h}, {"x": x, "y": y + h}]}}  # fmt: skip


def texts(fields):
    return join_masked(fields).split()


def test_name_right_of_label_is_hidden():
    fields = [box("성명", 10, 100), box("홍길동", 100, 100), box("주민등록번호", 300, 100)]
    assert texts(fields) == ["성명", "[이름]", "주민등록번호"]


def test_label_split_into_characters_and_scrambled_reading_order():
    fields = [
        box("성", 10, 100, 16),
        box("명", 60, 100, 16),
        box("탁", 120, 100, 16),
        box("민", 140, 100, 16),
        box("서", 160, 100, 16),
    ]
    random.Random(3).shuffle(fields)
    assert join_masked(fields).count("[이름]") == 1
    assert not {"탁", "민", "서"} & set(texts(fields))  # 읽는 순서가 뒤섞여도 이름 칸 글자는 남지 않는다


def test_name_that_text_rules_cannot_recognise():
    # 성씨 목록에 없는 성씨(빙) · 두 글자 이름 · 사 글자 이름 — 라벨 위치만으로 가린다
    for name in ("빙하나", "고은", "남궁민수"):
        fields = [box("환자명", 10, 100), box(name, 100, 100)]
        assert texts(fields) == ["환자명", "[이름]"]


def test_value_after_parenthesis_note_is_hidden():
    fields = [
        box("성명", 10, 100),
        box("(서명", 80, 100),
        box("또는", 140, 100),
        box("날인)", 190, 100),
        box("박명수", 260, 100),
    ]
    assert texts(fields)[-1] == "[이름]" and "박명수" not in join_masked(fields)


def test_other_labels_and_words_are_kept():
    # 라벨 옆이 다른 라벨(주민등록번호 · 전화번호 · 면허번호) · 양식 낱말이면 가리지 않는다
    for nxt in (
        "주민등록번호",
        "전화번호",
        "면허번호",
        "기호",
        "의료기관",
        "서명",
        "날인",
        "발행",
        "병원",
        "팩스",
        "휴대",
        "국민",
        "용량",
    ):  # 국민 · 용량은 mask.py 낱말 목록에만 있다
        assert texts([box("성명", 10, 100), box(nxt, 100, 100)]) == ["성명", nxt]
    assert name_boxes([box("성명", 10, 100), box("123-4567", 100, 100)]) == set()  # 한글이 아니면 가리지 않는다


def test_names_that_start_with_a_form_word_are_still_hidden():
    for name in ("기호준", "주민서", "조제원"):
        assert texts([box("성명", 10, 100), box(name, 100, 100)]) == ["성명", "[이름]"]


def test_far_or_other_row_is_not_hidden():
    assert name_boxes([box("성명", 10, 100), box("홍길동", 700, 100)]) == set()  # 라벨 높이의 8배보다 멀다
    assert name_boxes([box("성명", 10, 100), box("홍길동", 100, 200)]) == set()  # 다른 줄
    assert name_boxes([box("성명", 10, 100), box("홍길동", 100, 130)]) == set()  # 라벨 아래 칸은 보지 않는다


def test_single_characters_running_on_are_table_headers():
    fields = [box("성", 10, 100, 16), box("명", 40, 100, 16)] + [
        box(c, 80 + 25 * i, 100, 16) for i, c in enumerate("투약일수량")
    ]
    assert name_boxes(fields) == set()


def test_weak_label_needs_a_surname_shape():
    assert texts([box("이름", 10, 100), box("김환자", 100, 100)]) == ["이름", "[이름]"]
    assert texts([box("이름", 10, 100), box("아스피린", 100, 100)]) == ["이름", "아스피린"]  # 약 이름 칸 같은 일반 글


def test_weird_geometry_does_not_raise():
    bad = [{"inferText": "성명"}, {"inferText": "홍길동", "boundingPoly": {"vertices": []}}]
    assert name_boxes(bad) == set() and join_masked(bad) == "성명 홍길동"
    assert join_masked([]) == ""


def test_masking_twice_changes_nothing():
    fields = [box("성명", 10, 100), box("빙하나", 100, 100), box("환자", 10, 150), box("고은", 100, 150)]
    once = mask(join_masked(fields))
    assert mask(once) == once


def test_pipeline_raw_text_hides_name_box():
    data = json.loads(clova.SAMPLE.read_text(encoding="utf-8"))
    base = read(data, matcher(), CODES, today=TODAY)
    y = max(v["y"] for f in data["images"][0]["fields"] for v in f["boundingPoly"]["vertices"]) + 100
    data["images"][0]["fields"] += [box("성명", 10, y), box("빙하나", 90, y)]
    res = read(data, matcher(), CODES, today=TODAY)
    assert "빙하나" not in res.raw_text and res.raw_text.count("[이름]") == base.raw_text.count("[이름]") + 1
    assert [(r.dose, r.times, r.days) for r in res.rows] == [
        (r.dose, r.times, r.days) for r in base.rows
    ]  # 읽은 약 · 숫자는 그대로


def test_four_split_characters_that_are_not_a_name_are_kept():
    # "성명" 줄에 칸 이름이 한 글자씩 나온 경우: 성씨로 시작하지 않으면 이름이 아니다
    fields = [box("성", 10, 100, 16), box("명", 40, 100, 16)] + [
        box(c, 80 + 25 * i, 100, 16) for i, c in enumerate("투약일수")
    ]
    assert name_boxes(fields) == set()
    fields = [box("성", 10, 100, 16), box("명", 40, 100, 16)] + [
        box(c, 80 + 25 * i, 100, 16) for i, c in enumerate("빙하나")
    ]
    assert name_boxes(fields) == set()  # 성씨 목록에 없는 성씨가 글자마다 쪼개진 경우는 못 가린다 (알려진 한계)


def test_long_word_and_split_header_runs_are_kept():
    assert name_boxes([box("성명", 10, 100), box("홍길동홍길동", 100, 100)]) == set()  # 이름보다 긴 낱말
    header = [box("성명", 10, 100)] + [box(c, 80 + 25 * i, 100, 16) for i, c in enumerate("기팩스번호")]
    assert name_boxes(header) == set()  # 성씨(기)로 시작해도 한 글자씩 5글자 이어지면 칸 이름 (기 팩 스 번 호)
