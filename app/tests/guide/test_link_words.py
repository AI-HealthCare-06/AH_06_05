"""생활습관 안내의 약 연결: 칼륨이 오를 수 있는 약(ACE억제제, ARB, 이뇨제)에는 "의료진 확인"이 붙어야 함 (11/2 수인 확인)"""

from types import SimpleNamespace

import pytest

from app.services.guide import lifestyle


def _item(item_id: int, name: str) -> SimpleNamespace:
    return SimpleNamespace(id=item_id, drug=SimpleNamespace(item_name=name))


def _links(code: str, name: str) -> list[dict]:
    return lifestyle.build([code], [_item(1, name)])["medicationLinks"]


@pytest.mark.parametrize(
    "name",
    [
        "디오반정80밀리그램(발사르탄)",
        "아이스타플러스정80/5/10밀리그램(텔미사르탄,암로디핀,로수바스타틴)",
        "올메텍정20밀리그램(올메사르탄메독소밀)",
        "엑스포지정5/160밀리그램(암로디핀베실산염,발사르탄)",
        "코자정50밀리그램(로사르탄칼륨)",
        "캅토프릴정25밀리그램(캅토프릴)",
        "아프로벨정150밀리그램(이르베사르탄)",
        "인다파미드정1.5밀리그램(인다파미드)",
        "클로르탈리돈정25밀리그램(클로르탈리돈)",
        "토르세미드정5밀리그램(토라세미드)",
    ],
)
def test_htn_potassium_drugs_get_clinician_chip(name):
    links = _links("I10", name)
    # 복합제는 약 종류마다 연결이 따로 생기므로, 한 연결이라도 칩이 붙으면 됨(프런트는 연결마다 칩을 그림)
    assert any(link["requiresClinician"] for link in links), name


def test_calcium_blocker_stays_without_clinician_chip():
    links = _links("I10", "노바스크정5밀리그람(암로디핀베실산염)")
    assert links and not any(link["requiresClinician"] for link in links)


@pytest.mark.parametrize(
    "name",
    ["알닥톤정25밀리그램(스피로노락톤)", "디오반정80밀리그램(발사르탄)", "엘라프릴정5밀리그램(에날라프릴말레산염)"],
)
def test_ckd_potassium_line_gets_clinician_chip(name):
    links = _links("N18", name)
    assert links and all(link["requiresClinician"] for link in links), name
    assert any("염화칼륨" in a["text"] for link in links for a in link["actions"])


def test_spironolactone_has_its_own_htn_line_not_the_diuretic_line():
    """고혈압 이뇨제 줄(칼륨이 낮아질 수 있음)은 칼륨 보전 이뇨제를 뺀다고 적혀 있어, 스피로노락톤은 칼륨이 오를 수 있다는 별도 줄로 연결 (약학정보원 의약품 정보 근거)"""
    links = _links("I10", "알닥톤정25밀리그램(스피로노락톤)")
    assert len(links) == 1
    assert links[0]["requiresClinician"]
    text = " ".join(a["text"] for a in links[0]["actions"])
    assert "칼륨 보충제" in text and "혈액검사" in text
    assert "칼륨이 낮아질" not in text


def test_spironolactone_with_ckd_keeps_both_notices_and_chip():
    links = _links("N18", "알닥톤정25밀리그램(스피로노락톤)")
    assert links and all(link["requiresClinician"] for link in links)


def test_finerenone_gets_chip_with_ckd_only():
    name = "케렌디아정10밀리그램(피네레논)_(10mg/1정)"
    links = _links("N18", name)
    assert links and all(link["requiresClinician"] for link in links)
    assert _links("I10", name) == []


def test_goal_recommendation_words_are_unchanged():
    assert lifestyle.ingredient_words("ACE억제제·ARB (에날라프릴, 로사르탄 등)") == {"에날라프릴", "로사르탄"}
    assert lifestyle.ingredient_words("칼륨 보전 이뇨제·ACE억제제·ARB") == set()
