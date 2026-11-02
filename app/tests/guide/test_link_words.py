"""생활습관 안내의 약 연결: 칼륨이 오를 수 있는 약(ACE억제제, ARB, 이뇨제)에는 "의료진 확인"이 붙어야 함 (11/2 수인 확인)

약 이름·성분코드는 약제급여목록(drug_products)에 있는 실제 값이다. 복합제는 이름에 성분이 없어 성분코드로 찾는다.
"""

from types import SimpleNamespace

import pytest

from app.services.guide import lifestyle


def _item(item_id: int, name: str, ingr_code: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(id=item_id, drug=SimpleNamespace(item_name=name, ingr_code=ingr_code))


def _links(code: str, name: str, ingr_code: str | None = None) -> list[dict]:
    return lifestyle.build([code], [_item(1, name, ingr_code)])["medicationLinks"]


# (약 이름, 성분코드) — 이름에 성분이 적힌 약
NAMED = [
    ("디오반필름코팅정80밀리그램(발사르탄)_(80mg/1정)", "247101ATB"),
    ("카나브정60밀리그램(피마사르탄칼륨삼수화물)_(66.01mg/1정)", "515201ATB"),
    ("아프로벨정150밀리그람 (이르베사르탄)_(0.15g/1정)", "177301ATB"),
    ("라식스정(푸로세미드)_(40mg/1정)", "163801ATB"),
    ("토렘정10밀리그람(토라세미드)_(10mg/1정)", "242001ATB"),
    ("유레틴정(아조세미드)_(60mg/1정)", "112901ATB"),
    ("엑스원플러스정5/160/12.5밀리그램(암로디핀/발사르탄/클로르탈리돈)_(1정)", "750400ATB"),
]
# 이름에 성분이 없는 복합제 — 성분코드로만 찾을 수 있음
COMBO = [
    ("엑스포지정 5/160밀리그램_(1정)", "492800ATB"),
    ("코자플러스정_(1정)", "262500ATB"),
    ("올메텍플러스정20/12.5밀리그램_(1정)", "513600ATB"),
    ("아모잘탄정5/100밀리그램_(1정)", "502700ATB"),
    ("카나브플러스정60/12.5mg_(1정)", "522000ATB"),
    ("카나브플러스정120/12.5mg_(1정)", "526800ATB"),
    ("코자엑스큐정10/50밀리그램_(1정)", "513900ATB"),
]


@pytest.mark.parametrize(("name", "ingr"), NAMED + COMBO)
def test_htn_potassium_drugs_get_clinician_chip(name, ingr):
    links = _links("I10", name, ingr)
    # 복합제는 약 종류마다 연결이 따로 생기므로, 한 연결이라도 칩이 붙으면 됨(프런트는 연결마다 칩을 그림)
    assert any(link["requiresClinician"] for link in links), name


@pytest.mark.parametrize(("name", "ingr"), COMBO)
def test_combo_without_ingredient_in_name_needs_ingr_code(name, ingr):
    assert not any(link["requiresClinician"] for link in _links("I10", name, None)), name
    assert any(link["requiresClinician"] for link in _links("I10", name, ingr)), name


def test_calcium_blocker_stays_without_clinician_chip():
    links = _links("I10", "노바스크정5밀리그람(암로디핀베실산염)_(6.944mg/1정)", "107601ATB")
    assert links and not any(link["requiresClinician"] for link in links)


@pytest.mark.parametrize(
    ("name", "ingr"),
    [
        ("알닥톤필름코팅정25밀리그람(스피로노락톤)_(25mg/1정)", "231101ATB"),
        ("디오반필름코팅정80밀리그램(발사르탄)_(80mg/1정)", "247101ATB"),
        ("케렌디아정10밀리그램(피네레논)_(10mg/1정)", "729201ATB"),
        ("엑스포지정 5/160밀리그램_(1정)", "492800ATB"),
    ],
)
def test_ckd_potassium_line_gets_clinician_chip(name, ingr):
    links = _links("N18", name, ingr)
    assert links and all(link["requiresClinician"] for link in links), name
    assert any("염화칼륨" in a["text"] for link in links for a in link["actions"])


def test_spironolactone_has_its_own_htn_line_not_the_diuretic_line():
    """고혈압 이뇨제 줄(칼륨이 낮아질 수 있음)은 칼륨 보전 이뇨제를 뺀다고 적혀 있어, 스피로노락톤은 칼륨이 오를 수 있다는 별도 줄로 연결 (약학정보원 의약품 정보 근거)"""
    links = _links("I10", "알닥톤필름코팅정25밀리그람(스피로노락톤)_(25mg/1정)", "231101ATB")
    assert len(links) == 1
    assert links[0]["requiresClinician"]
    text = " ".join(a["text"] for a in links[0]["actions"])
    assert "칼륨 보충제" in text and "혈액검사" in text


def test_spironolactone_with_ckd_keeps_both_notices_and_chip():
    """고혈압+만성콩팥병: 고혈압 줄과 콩팥병 줄이 둘 다 나오고 모두 의료진 확인이 붙음"""
    result = lifestyle.build(
        ["I10", "N18"], [_item(1, "알닥톤필름코팅정25밀리그람(스피로노락톤)_(25mg/1정)", "231101ATB")]
    )
    links = result["medicationLinks"]
    assert len(links) == 2
    assert all(link["requiresClinician"] for link in links)
