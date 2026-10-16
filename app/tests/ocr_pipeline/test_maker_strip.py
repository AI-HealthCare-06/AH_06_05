"""처방전 약 이름 끝에 붙어 읽힌 제조사 떼기 (실제 CLOVA 결과 n4에서 발견) — LLM을 부르기 전 정규식 정리"""

import pytest

from app.services.drug_names import maker_pattern, strip_maker
from app.services.ocr.matcher import FOUND, NOT_FOUND, NameMatcher

MAKERS = ["제일약품(주)", "(주)한국팜비오", "한국화이자제약(주)", "한미약품(주)", "한국유나이티드제약"]


@pytest.mark.parametrize(
    "read, expected",
    [
        ("-엘로시드캡슬7.5mg(엘록시캄)제일약품(주)", "엘로시드캡슬7.5mg(엘록시캄)"),  # ")" 뒤 → 규칙만으로 뗌
        ("-메디아벤엘정(나프타존)(주)한국팜비오-", "메디아벤엘정(나프타존)"),  # 앞 "(주)" 형태 + 끝 줄표
        (
            "노바스크정5밀리그램(암로디핀베실산염) 한국화이자제약(주)",
            "노바스크정5밀리그램(암로디핀베실산염)",
        ),  # 공백 뒤
        (
            "리피토정10밀리그램(아토르바스타틴칼슘삼수화물)",
            "리피토정10밀리그램(아토르바스타틴칼슘삼수화물)",
        ),  # 제조사 없음 → 그대로
        (
            "넥실렌에스정제일약품(주)",
            "넥실렌에스정제일약품(주)",
        ),  # 이름에 붙어 있으면 규칙만으로는 안 뗌 (이름까지 지우는 것을 막음)
        ("아스피린프로택트쟁100밀리그람", "아스피린프로택트쟁100밀리그람"),
    ],
)
def test_general_rule_strips_only_makers_after_a_boundary(read, expected):
    assert strip_maker(read) == expected


def test_glued_maker_is_stripped_only_when_it_exactly_matches_a_known_maker():
    pat = maker_pattern(MAKERS)
    assert strip_maker("-넥실렌에스정제일약품(주)", pat) == "넥실렌에스정"
    assert strip_maker("넥실렌에스정한미약품(주)", pat) == "넥실렌에스정"
    assert (
        strip_maker("넥실렌에스정제일약품", pat) == "넥실렌에스정제일약품"
    )  # "(주)"가 없으면 이름의 일부일 수 있어 안 뗌
    assert strip_maker("한국유나이티드제약", pat) == "한국유나이티드제약"  # (주) 없는 제조사 이름은 패턴에 넣지 않음
    assert maker_pattern([]) is None and maker_pattern(["", "(주)없음"]) is not None


def test_matcher_finds_the_drug_once_the_maker_is_removed():
    products = [
        ("1", "넥실렌에스정[애엽이소프로판올연조엑스(20→1)]_(90mg/1정)"),
        ("2", "메디아벤엘정(나프타존)_(10mg/1정)"),
    ]
    plain = NameMatcher(products)
    with_makers = NameMatcher(products, makers=MAKERS)
    assert plain.decide("-넥실렌에스정제일약품(주)").status == NOT_FOUND  # 제조사 이름을 모르면 못 찾음
    d = with_makers.decide("-넥실렌에스정제일약품(주)")
    assert d.status == FOUND and d.candidates[0].edi_code == "1"
    for m in (plain, with_makers):  # 경계가 있는 제조사는 제조사 목록 없이도 뗌
        assert m.decide("-메디아벤엘정(나프타존)(주)한국팜비오-").status == FOUND
    assert with_makers.without_maker("-메디아벤엘정(나프타존)(주)한국팜비오-") == "메디아벤엘정(나프타존)"
