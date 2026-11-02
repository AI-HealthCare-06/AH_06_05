"""화면에 보내는 약 이름: 약제급여목록 제품명의 수출명을 뗌 (원본 528개 제품, 10/29 배포 서버에서 스로펜 확인)"""

import pytest

from app.services.drug_names import base_name, display_name

CASES = [
    ("스로펜정(이부프로펜) 수출명:Korus Ibuprofen Tab._(0.2g/1정)", "스로펜정(이부프로펜)"),
    ("클란자에스연질캡슐(아세클로페낙)(수출명:SpeenacSoftCaps.)_(0.1g/1캡슐)", "클란자에스연질캡슐(아세클로페낙)"),
    ("아로탈정(아세클로페낙)(수출명:아로세탈정(Arocetaltablet))_(0.1g/1정)", "아로탈정(아세클로페낙)"),
    ("한국유나이티드반코마이신염산염주1그램((수출명:Vancozine 1g)_(1g/1병)", "한국유나이티드반코마이신염산염주1그램"),
    ("노바스크정5밀리그람(암로디핀베실산염)_(6.944mg/1정)", "노바스크정5밀리그람(암로디핀베실산염)"),
    # 수출명 앞의 [ < / , 와 나라 이름까지 뗌 (#152 리뷰: 원본 528개 중 39개가 괄호가 열린 채 끝났음)
    ("그리자이드정(글리클라짓)[캄보디아수출명:멜리크론정(Mellicron)]_(80mg/1정)", "그리자이드정(글리클라짓)"),
    (
        "뉴세프주1그람(세프트리악손나트륨수화물)[수출명:CEFAXONE INJ.1g]_(1g/1병)",
        "뉴세프주1그람(세프트리악손나트륨수화물)",
    ),
    (
        "쎄릭손주2그램(세프트리악손나트륨수화물)/수출명:쎄릭손2그램정주(세프트리악손나트륨)_(2g/1병)",
        "쎄릭손주2그램(세프트리악손나트륨수화물)",
    ),
    ("타나민정(은행엽건조엑스)<수출명:디멘탈정(은행엽건조엑스)>_(40mg/1정)", "타나민정(은행엽건조엑스)"),
    ("케토톱플라스타(케토프로펜)(인도수출명:케토패취, 대만수출명:관건(關建))_(70㎠/1매)", "케토톱플라스타(케토프로펜)"),
    ("명인브로마제팜정3밀리그람[(수출명:로지팜정3밀리그람(브로마제팜)]_(3mg/1정)", "명인브로마제팜정3밀리그람"),
    (
        "유한2%염산리도카인.에피네프린주사(1:100000)[군납명:염산리도카인2%에리네프린주사(1:100,000)][수출명:에피카인주사(1:100,000)]_(1.8mL)",
        "유한2%염산리도카인.에피네프린주사(1:100000)[군납명:염산리도카인2%에리네프린주사(1:100,000)]",
    ),
    # 괄호 안 성분 뒤에 쉼표로 수출명이 이어지면 성분은 남기고 괄호를 닫음
    ("파무정(프랄리독심염화물,수출명:PralidoximChlorideTab.)_(0.5g/1정)", "파무정(프랄리독심염화물)"),
    # 이름 앞부분을 넓게 지우면 빈 이름이 되는 것 (#152 리뷰 주의)
    ("대원아미노필린정[수출명:아미핀정(Amipinetab.)]_(아미노필린수화물, 0.1g/1정)", "대원아미노필린정"),
    ("크목실린정625밀리그램[수출명: 클루목스정625mg(CLUMOX TABLET 625mg)]_(1정)", "크목실린정625밀리그램"),
]


@pytest.mark.parametrize(("raw", "want"), CASES)
def test_display_name_drops_export_name(raw, want):
    assert display_name(raw) == want


def test_base_name_keeps_export_name_for_matching():
    """이름 맞추기(base_name, normalize_name)는 그대로 둠. DB의 item_name_norm과 어긋나지 않게"""
    assert "수출명" in base_name("스로펜정(이부프로펜) 수출명:Korus Ibuprofen Tab._(0.2g/1정)")


def test_ingredient_label_prefers_korean_name_in_parentheses():
    """경고 자세히 보기의 성분이 영어로 보이던 것 (11/2 E2E)"""
    from app.services.drug_names import ingredient_label

    assert (
        ingredient_label("노바스크정5밀리그람(암로디핀베실산염)_(6.944mg/1정)", "amlodipine besylate")
        == "암로디핀베실산염"
    )
    assert (
        ingredient_label("아이스타플러스정80/5/10밀리그램(텔미사르탄,암로디핀,로수바스타틴)_(1정)", "x")
        == "텔미사르탄,암로디핀,로수바스타틴"
    )
    # 이름에 성분이 없으면 흔한 성분만 한글로, 나머지는 영어 그대로
    assert ingredient_label("알파아세트아미노펜정500밀리그람_(0.5g/1정)", "acetaminophen") == "아세트아미노펜"
    assert ingredient_label("게보린정_(1정)", "caffeine anhydrous") == "무수카페인"
    assert ingredient_label("어떤약정_(1정)", "polmacoxib") == "polmacoxib"
    assert ingredient_label("어떤약정_(1정)", None) is None
    assert (
        ingredient_label("리피토정10밀리그램(아토르바스타틴칼슘삼수화물)_(1정)", "아토르바스타틴") == "아토르바스타틴"
    )
    # 수출명 괄호는 성분으로 보지 않음
    assert ingredient_label("파무정(수출명:Pamu)_(1정)", "pamu") == "pamu"
