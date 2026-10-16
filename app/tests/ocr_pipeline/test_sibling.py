"""형제 약 확인 — 읽힌 이름이 목록에 있어도 글자 하나 차이의 다른 성분 약이 있으면 자동 확정하지 않고 사용자가 고르게 한다
(10/14 시험: 로글리코엠정을 로글리코정으로 읽으면 글자만으로는 오타와 다른 약을 구별할 수 없어 틀린 약이 확정됨)"""

import json

from app.services.ocr import clova
from app.services.ocr import matcher as mod
from app.services.ocr.matcher import AMBIGUOUS, FOUND, NameMatcher
from app.services.ocr.pipeline import SIBLING_FLAG, read

PRODUCTS = [
    ("100000001", "로글리코정2밀리그램(글리메피리드)_(2mg/1정)"),
    ("100000002", "로글리코엠정2/500밀리그램(글리메피리드/메트포르민염산염)_(1정)"),
    ("100000003", "글리마릴정1밀리그램(글리메피리드)_(1mg/1정)"),
    ("100000004", "글리마릴엠정1/250밀리그램(글리메피리드/메트포르민염산염)_(1정)"),
    ("100000005", "건일몬테루카스트정10밀리그램(몬테루카스트나트륨)_(10mg/1정)"),
    ("100000006", "건일몬테루카스트츄정10밀리그램(몬테루카스트나트륨)_(10mg/1정)"),
    ("100000007", "노바스크정5밀리그람(암로디핀베실산염)_(6.944mg/1정)"),
    ("100000008", "다이아벡스정500밀리그램(메트포르민염산염)_(0.5g/1정)"),
    ("100000009", "알수없는정10밀리그램_(10mg/1정)"),
    ("100000010", "알수없는엠정10밀리그램_(10mg/1정)"),
]
INGR = {
    "100000001": "G1",
    "100000002": "G2",
    "100000003": "G1",
    "100000004": "G2",
    "100000005": "M1",
    "100000006": "M1",  # 같은 성분 (제형만 다름) → 확인할 필요 없음
    "100000007": "A1",
    "100000008": "D1",
    "100000009": None,  # 성분 코드를 모름 → 다르다고 보고 확인
    "100000010": None,
}


def m(ingredients=INGR) -> NameMatcher:
    return NameMatcher(PRODUCTS, ingredients=ingredients)


def test_shorter_name_with_a_different_ingredient_sibling_becomes_a_choice():
    d = m().decide("로글리코정2밀리그램(글리메피리드)")  # 목록에 있는 이름이지만 '엠'이 빠져 읽힌 것일 수도 있음
    assert d.status == AMBIGUOUS and d.sibling
    assert [c.edi_code for c in d.candidates] == ["100000001", "100000002"]  # 읽은 이름의 약이 1번, 형제가 2번


def test_longer_name_with_a_different_ingredient_sibling_becomes_a_choice():
    d = m().decide("글리마릴엠정1/250밀리그램(글리메피리드/메트포르민염산염)")
    assert d.status == AMBIGUOUS and d.sibling
    assert [c.edi_code for c in d.candidates] == ["100000004", "100000003"]


def test_same_ingredient_sibling_is_not_asked():
    d = m().decide("건일몬테루카스트정10밀리그램(몬테루카스트나트륨)")
    assert d.status == FOUND and not d.sibling


def test_unknown_ingredient_counts_as_different():
    d = m().decide("알수없는정10밀리그램")
    assert d.status == AMBIGUOUS and d.sibling


def test_names_without_a_sibling_stay_found():
    for name in ("노바스크정5밀리그람(암로디핀베실산염)", "다이아벡스정500밀리그램(메트포르민염산염)"):
        d = m().decide(name)
        assert d.status == FOUND and not d.sibling, name


def test_check_is_off_without_ingredient_data_or_with_the_switch_off_or_when_skipped(monkeypatch):
    name = "로글리코정2밀리그램(글리메피리드)"
    assert m(None).decide(name).status == FOUND  # 성분 자료가 없으면 검사하지 않음
    assert m().decide(name, siblings=False).status == FOUND  # LLM 추천 · 직접 검색 경로
    monkeypatch.setattr(mod.config, "OCR_SIBLING_CONFIRM", False)
    assert m().decide(name).status == FOUND


def test_many_siblings_show_up_to_five_choices_or_top_n_if_larger():
    """형제가 많은 이름은 3개로는 진짜 약이 빠진다 (10/14 측정: 3개 83% · 5개 94%) → 읽은 이름의 약 + 형제로 5개까지, top_n이 더 크면 그만큼"""
    products = [("200000000", "세티정(토피라메이트)_(0.1g/1정)")] + [
        (f"20000000{i}", f"{p}세티정(성분{i})_(1정)") for i, p in enumerate("아레마가나다라", start=1)
    ]
    ingr = {edi: f"I{i}" for i, (edi, _) in enumerate(products)}
    mm = NameMatcher(products, ingredients=ingr)
    d = mm.decide("세티정(토피라메이트)")
    assert d.status == AMBIGUOUS and len(d.candidates) == 5 and d.candidates[0].edi_code == "200000000"
    assert len({c.edi_code for c in d.candidates}) == 5
    assert len(mm.decide("세티정(토피라메이트)", top_n=7).candidates) == 7
    assert len(mm.decide("세티정(토피라메이트)", top_n=1).candidates) == 5  # top_n이 작아도 형제 확인은 5개까지


def test_closest_siblings_are_kept_first_when_there_are_too_many():
    """후보가 5개로 잘릴 때는 질문 이름과 글자가 가장 가까운 형제부터 남긴다"""
    products = [("300000000", "세티정(토피라메이트)_(0.1g/1정)")] + [
        (f"30000000{i}", f"{p}세티정({x})_(1정)")
        for i, (p, x) in enumerate(
            zip(
                "아레마가나다라",
                ("성분가", "성분나", "성분다", "성분라", "성분마", "성분바", "토피라메이트"),
                strict=True,
            ),
            start=1,
        )
    ]
    ingr = {edi: f"I{i}" for i, (edi, _) in enumerate(products)}
    d = NameMatcher(products, ingredients=ingr).decide("세티정(토피라메이트)")
    assert len(d.candidates) == 5
    assert d.candidates[1].item_name.startswith(
        "라세티정(토피라메이트)"
    )  # 7번째로 만든 형제가 가장 가까움 → 첫 형제 자리


def test_sibling_index_is_built_once_and_prepare_builds_it():
    mm = m()
    mm.prepare()
    first = mm._sib
    assert first and mm._siblings() is first
    assert mm._sib is first


def test_pipeline_flags_the_row_and_leaves_other_rows_alone():
    data = json.loads(clova.SAMPLE.read_text(encoding="utf-8"))
    products = [*PRODUCTS, ("100000011", "노바스크엠정5밀리그람(암로디핀베실산염/로사르탄)_(1정)")]
    mm = NameMatcher(products, ingredients={**INGR, "100000011": "A2"})
    res = read(data, mm, {"I10": "본태성 고혈압"})
    first = res.rows[0]
    assert first.read_name.startswith("노바스크정")
    assert first.decision.status == AMBIGUOUS and first.decision.sibling
    assert first.decision.candidates[0].edi_code == "100000007"
    assert SIBLING_FLAG in first.flags and first.suggested_by is None  # 추천(오타 보정)이 아님
    assert all(SIBLING_FLAG not in r.flags for r in res.rows[1:])
