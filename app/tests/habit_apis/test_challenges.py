"""실천 목표 추천 규칙 (REQ-110). 9/23에 정한 세 가지만 팩트표 근거가 있을 때 추천 (10/30 수인 결정). AI 없음"""

from app.services import challenges
from app.services.guide import lifestyle


def keys(items):
    return [i["key"] for i in items]


def by_key(items, key):
    return next(i for i in items if i["key"] == key)


def test_hypertension_soup_and_walk_but_not_alcohol():
    # 고혈압 팩트표는 절주(남 2잔, 여 1잔 이하)라서 "술 마시지 않기"는 추천하지 않음
    items = challenges.recommend(["I10"], [], "monthly")
    assert keys(items) == ["soup", "walk"]
    soup, walk = items
    assert soup["title"] == "국물 남기기" and soup["goal_type"] == "check" and soup["reason_label"] == "고혈압"
    assert soup["desc"] == "1일 나트륨 2,000mg 이하 (소금 약 5g)"
    assert walk["title"] == "빠르게 걷기 30분" and walk["goal_type"] == "quantity"
    assert walk["target_value"] == 30 and walk["unit"] == "분" and walk["caution_label"] is None


def test_reasons_join_every_disease_with_backing():
    items = challenges.recommend(["I10", "N18"], [], "monthly")
    assert by_key(items, "soup")["reason_label"] == "고혈압, 만성신장병"
    assert by_key(items, "walk")["reason_label"] == "고혈압"  # 만성신장병 팩트표에는 걷기가 없음


def test_dyslipidemia_walk_and_alcohol():
    items = challenges.recommend(["E78"], [], "monthly")
    assert keys(items) == ["walk", "alcohol"]
    alcohol = by_key(items, "alcohol")
    assert alcohol["title"] == "술 마시지 않기" and alcohol["reason_label"] == "이상지질혈증"
    assert alcohol["desc"] == "금주 또는 절주"


def test_diabetes_walk_and_sulfonylurea_alcohol():
    assert keys(challenges.recommend(["E11"], ["다이아벡스정500밀리그램(메트포르민염산염)"], "monthly")) == ["walk"]
    items = challenges.recommend(["E11"], ["아마릴정2밀리그램(글리메피리드)"], "monthly")
    assert keys(items) == ["walk", "alcohol"]
    assert by_key(items, "alcohol")["reason_label"] == "약과 함께"
    assert by_key(items, "alcohol")["desc"] == "음주 시 저혈당 위험 증가"


def test_ischemic_heart_walk_by_clinician_intensity():
    # 허혈성심질환 팩트표: 심장재활 운동은 의료진이 정한 강도로. 다른 질환이 걷기를 권해도 이 모양으로 바꿈
    items = challenges.recommend(["I10", "I25"], [], "monthly")
    walk = by_key(items, "walk")
    assert walk["title"] == "걷기" and walk["goal_type"] == "check"
    assert walk["target_value"] is None and walk["unit"] is None
    assert walk["caution_label"] == "의료진이 정한 강도로" and walk["reason_label"] == "고혈압, 허혈성심질환"
    assert walk["desc"] == "의료진이 정한 강도로 주 5회. 시술·수술 후에는 반드시 의료진 승인 후 시작"


def test_alcohol_skipped_when_user_does_not_drink():
    assert keys(challenges.recommend(["E78"], [], "none")) == ["walk"]
    assert keys(challenges.recommend(["E78"], [], None)) == ["walk", "alcohol"]  # 건강 정보가 없으면 그대로


def test_no_disease_no_recommendation():
    # 팩트표는 질환별이고 약 링크도 질환 아래에 있어, 질환이 없으면 약을 먹어도 추천하지 않음 (생활습관 탭과 같은 기준, 10/30 수인 결정)
    assert challenges.recommend([], ["타이레놀정500밀리그람(아세트아미노펜)"], "monthly") == []
    assert challenges.recommend(["J00"], [], "monthly") == []


def test_every_source_exists_in_fact_table():
    # 팩트표가 바뀌어 항목 이름이 달라지면 여기서 먼저 알게
    names = {d["id"]: {ls["category"] for ls in d["lifestyle"]} for d in lifestyle.facts()["diseases"]}
    for c in challenges.CHALLENGES:
        for s in c.sources:
            if s.category:
                assert s.category in names[s.disease], (c.key, s)
    assert challenges.recommend(["I69"], [], "monthly")[0]["desc"] == "금주 권장"
