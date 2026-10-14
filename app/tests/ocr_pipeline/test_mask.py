"""OCR 원문 마스킹 — 이름 · 주민번호 · 전화번호 등은 가리고, 병원 · 약 · 숫자는 남긴다 (수인님 결정 10/14)"""

import json

import pytest

from app.services.ocr import clova
from app.services.ocr.mask import NAME, PHONE, RRN, mask


def sample_text() -> str:
    data = json.loads(clova.SAMPLE.read_text(encoding="utf-8"))
    return " ".join(f["inferText"] for f in data["images"][0]["fields"])


def test_sample_prescription_hides_patient_doctor_and_phone_but_keeps_the_rest():
    out = mask(sample_text())
    for secret in ("홍길동", "김의사", "02-000-0000"):
        assert secret not in out
    assert f"환자 성명 {NAME}" in out and f"전화번호 {PHONE}" in out and f"처방 의료인 {NAME}" in out
    for kept in (
        "가나다내과의원",
        "1955년생",
        "110,E11",
        "노바스크정5밀리그램",
        "1 2 30",
        "식후 30분 복용",
        "2026년 10월 01일",
    ):
        assert kept in out


@pytest.mark.parametrize(
    "text",
    [
        "주민등록번호 900101-1234567",
        "주민등록번호 900101 - 1234567",  # OCR이 공백을 넣음
        "주민등록번호 900101–1234567",  # 엔 대시
        "주민등록번호 9001011234567",  # 붙여 쓴 13자리
        "주민등록번호 900101-1******",  # 양식에 뒷자리가 가려져 있음
        "주민등록번호 900101-1",  # 뒷자리 첫 숫자만 읽힘
        "외국인등록번호 900101-5234567",
    ],
)
def test_resident_numbers_are_hidden_in_all_ocr_shapes(text):
    out = mask(text)
    assert RRN in out and "900101" not in out


@pytest.mark.parametrize(
    "text",
    [
        "전화번호 02-000-0000",
        "전화번호 010-1234-5678",
        "전화번호 010 1234 5678",
        "전화번호 01012345678",
        "전화 031)123-4567",
    ],
)
def test_phone_numbers_are_hidden(text):
    out = mask(text)
    assert PHONE in out and not any(ch.isdigit() for ch in out.replace("[전화번호]", ""))


def test_other_identifiers_are_hidden_but_labels_stay():
    out = mask("면허번호 제12345호 요양기관기호 12345678 보험증번호 A1234567 연락 test.user@mail.co.kr")
    assert "12345" not in out and "A1234567" not in out and "test.user" not in out
    assert "면허번호 [면허번호]" in out and "요양기관기호 [기관기호]" in out and "보험증번호 [보험번호]" in out
    assert "[이메일]" in out


def test_names_after_labels_only():
    assert mask("환자 성명 이영희 전화번호") == f"환자 성명 {NAME} 전화번호"
    assert mask("처방 의료인의 성명 박의사 (서명 또는 날인)") == f"처방 의료인의 성명 {NAME} (서명 또는 날인)"
    assert mask("의료인 질병분류기호 E11") == "의료인 질병분류기호 E11"  # 다음 라벨을 이름으로 오인하지 않음
    assert mask("의료기관 명칭 가나다내과의원") == "의료기관 명칭 가나다내과의원"  # 병원 이름은 남김
    assert mask("성명 면허종류 의사") == "성명 면허종류 의사"


def test_drug_lines_dates_and_numbers_are_untouched():
    text = "노바스크정5밀리그램(암로디핀베실산염) 1 1 30 아스피린프로텍트정100밀리그램 1 3 7 교부번호 2026년 10월 01일 제 00012 호 64900:1971"
    assert mask(text) == text


def test_masking_is_idempotent_and_empty_safe():
    once = mask(sample_text() + " 주민등록번호 900101-1234567 면허번호 제12345호")
    assert mask(once) == once
    assert mask("") == ""
