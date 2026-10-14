"""비슷한 이름 추천 (글자 3개 조각 유사도, pg_trgm 방식) — 글자 하나가 바뀐 이름은 후보로 올리고, 다른 약은 올리지 않는다"""

import json

from app.services.ocr import clova
from app.services.ocr.matcher import AMBIGUOUS, FOUND, NOT_FOUND, NameMatcher, similarity, trigrams
from app.services.ocr.pipeline import SIMILAR_FLAG, read

PRODUCTS = [
    ("641900040", "노바스크정5밀리그람(암로디핀베실산염)_(6.944mg/1정)"),
    ("644300010", "다이아벡스정500밀리그램(메트포르민염산염)_(0.5g/1정)"),
    ("645600020", "리피토정10밀리그램(아토르바스타틴칼슘삼수화물)_(10.85mg/1정)"),
    ("648800030", "아스피린프로텍트정100밀리그람_(0.1g/1정)"),
    ("650000001", "모사프리드정5밀리그램(모사프리드시트르산염수화물)_(5.29mg/1정)"),
    ("650000002", "세레콕시브캡슐200밀리그램(세레콕시브)_(0.2g/1캡슐)"),
    ("650000003", "멜로시드캡슐7.5밀리그램(멜록시캄)_(7.5mg/1캡슐)"),
]
CODES = {"I10": "본태성 고혈압"}


def m() -> NameMatcher:
    return NameMatcher(PRODUCTS)


def test_trigrams_follow_pg_trgm_rules_on_decomposed_hangul():
    """PostgreSQL pg_trgm과 같은 조각 · 같은 값 (10/14에 실제 pg_trgm과 400쌍을 대조해 모두 일치 — 한글은 자모로 푼 글자에 적용)"""
    assert trigrams("A(b)") == frozenset({"  a", " a ", "  b", " b "})  # 소문자 · 괄호는 낱말을 나눔
    assert trigrams("") == frozenset()
    assert trigrams("가") == frozenset({"  \u1100", " \u1100\u1161", "\u1100\u1161 "})  # ㄱ ㅏ
    assert similarity(trigrams("고혈압"), trigrams("고혈압")) == 1.0
    assert similarity(trigrams("고혈압"), trigrams("abc")) == 0.0
    # 글자 하나가 비슷한 글자로 읽히면(엘→멜) 음절 단위로 자른 값(0.25)보다 훨씬 높다
    assert similarity(trigrams("엘로시드"), trigrams("멜로시드")) > 0.5


def test_threshold_is_configurable_and_zero_turns_it_off(monkeypatch):
    from app.services.ocr import matcher as mod

    typo = "노바스정5밀리그람(암로디핀베실산염)"
    assert m().similar(typo) is not None
    monkeypatch.setattr(mod.config, "OCR_SIMILAR_MIN", 0.0)
    assert m().similar(typo) is None  # 꺼짐
    monkeypatch.setattr(mod.config, "OCR_SIMILAR_MIN", 0.99)
    assert m().similar(typo) is None  # 기준이 높으면 추천하지 않음


def test_changed_or_missing_letter_becomes_a_suggestion_never_auto_confirmed():
    for typo, edi in (
        ("노바스정5밀리그람(암로디핀베실산염)", "641900040"),  # 글자 하나가 빠짐 (규칙은 못 찾음)
        ("누바스크정5밀리그람(암로디핀베실산염)", "641900040"),  # 글자 하나가 비슷한 글자로
        ("노바스크정5밀리그람(암로디핀베실산염", "641900040"),  # 끝 괄호가 잘림
        ("아스피린프로택트정100밀리그람", "648800030"),  # ㅔ → ㅐ (실제 CLOVA 오독)
        ("엘로시드캡슐7.5밀리그램(엘록시캄)", "650000003"),  # 멜 → 엘 (실제 CLOVA 오독)
        ("다이아벡스젖500밀리그램(메트포르민염산염)", "644300010"),
    ):
        sug = m().similar(typo)
        assert sug is not None and sug.status == AMBIGUOUS and sug.candidates[0].edi_code == edi, typo
    assert (
        m().decide("노바스정5밀리그람(암로디핀베실산염)").status == NOT_FOUND
    )  # 이 경우 규칙 단독으로는 못 찾아서 추천이 의미가 있다


def test_suggestions_are_always_choices_never_confirmed():
    """오타와 비슷한 다른 약은 글자만으로 구별할 수 없다 → 추천은 어떤 입력에서도 고르는 후보(AMBIGUOUS)로만 낸다"""
    mm = m()
    queries = [
        "노바스정5밀리그람(암로디핀베실산염)",
        "모시프리드정5밀리그램(모사프리드시트르산염수화물)",
        "세레콕시브캡슐100밀리그램(세레콕시브)",
        "멜로시드캡슐15밀리그램(멜록시캄)",
        "아스피린프로텍트정50밀리그람",
    ]
    got = [mm.similar(q) for q in queries]
    assert any(g is not None for g in got)
    assert all(g is None or g.status == AMBIGUOUS for g in got)


def test_unrelated_names_and_junk_get_no_suggestion():
    mm = m()
    for name in (
        "로페콕시브정25밀리그램(로페콕시브)",  # 급여목록에 없는 약: 세레콕시브로 끌려가지 않음
        "처방의약품의명칭",
        "용법식후30분복용",
        "병원",  # 너무 짧음
        "",
    ):
        assert mm.similar(name) is None, name


def test_exact_names_are_still_found_by_the_rule_not_the_suggestion():
    d = m().decide("다이아벡스정 500mg(메트포르민염산염)")
    assert d.status == FOUND


def test_empty_index_gives_no_suggestion():
    assert NameMatcher([]).similar("노바스크정5밀리그람") is None


def test_pipeline_marks_the_row_as_needing_confirmation_and_flags_it():
    data = json.loads(clova.SAMPLE.read_text(encoding="utf-8"))
    for f in data["images"][0]["fields"]:
        if f["inferText"].startswith("노바스크정5밀리그램"):
            f["inferText"] = "노바스정5밀리그램(암로디핀베실산염)"
    res = read(data, m(), CODES)
    first = res.rows[0]
    assert first.decision.status == AMBIGUOUS and first.decision.candidates[0].edi_code == "641900040"
    assert SIMILAR_FLAG in first.flags and first.suggested_by == "similar"
    assert all(r.suggested_by is None for r in res.rows[1:])
    assert all(SIMILAR_FLAG not in r.flags for r in res.rows[1:])  # 나머지 줄은 그대로
