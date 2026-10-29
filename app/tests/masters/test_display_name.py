"""화면에 보내는 약 이름: 약제급여목록 제품명의 수출명을 뗌 (원본 528개 제품, 10/29 배포 서버에서 스로펜 확인)"""

import pytest

from app.services.drug_names import base_name, display_name

CASES = [
    ("스로펜정(이부프로펜) 수출명:Korus Ibuprofen Tab._(0.2g/1정)", "스로펜정(이부프로펜)"),
    ("클란자에스연질캡슐(아세클로페낙)(수출명:SpeenacSoftCaps.)_(0.1g/1캡슐)", "클란자에스연질캡슐(아세클로페낙)"),
    ("아로탈정(아세클로페낙)(수출명:아로세탈정(Arocetaltablet))_(0.1g/1정)", "아로탈정(아세클로페낙)"),
    ("한국유나이티드반코마이신염산염주1그램((수출명:Vancozine 1g)_(1g/1병)", "한국유나이티드반코마이신염산염주1그램"),
    ("노바스크정5밀리그람(암로디핀베실산염)_(6.944mg/1정)", "노바스크정5밀리그람(암로디핀베실산염)"),
]


@pytest.mark.parametrize(("raw", "want"), CASES)
def test_display_name_drops_export_name(raw, want):
    assert display_name(raw) == want


def test_base_name_keeps_export_name_for_matching():
    """이름 맞추기(base_name, normalize_name)는 그대로 둠. DB의 item_name_norm과 어긋나지 않게"""
    assert "수출명" in base_name("스로펜정(이부프로펜) 수출명:Korus Ibuprofen Tab._(0.2g/1정)")
