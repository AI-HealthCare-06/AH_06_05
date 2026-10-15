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


@pytest.mark.parametrize(
    "text, hidden",
    [
        ("환자 성 명 홍길동", "홍길동"),  # OCR이 라벨 글자 사이에 공백을 넣음
        ("이 름 : 박철수", "박철수"),
        ("의 료 인 성 명 김의사", "김의사"),
        ("주민 등록 번호 900101 1234567", "900101"),  # 하이픈이 빠지고 공백이 들어감
        ("주민등록번호: 900101–1******", "900101"),
        ("외국인등록번호 900101 5234567", "900101"),
        ("전화 번호 010 1234 5678", "5678"),
        ("핸드폰 010-1234-5678", "1234"),
        ("연락처 (02) 123-4567", "4567"),
        ("전화번호 123-4567", "4567"),  # 지역번호가 없는 번호는 라벨로만 알 수 있음
        ("휴대폰 1234 5678", "5678"),
        ("생년월일 1990.01.01", "1990"),
        ("생년월일 1990년 1월 5일", "1990"),
        ("생년월일 19900101", "1990"),
    ],
)
def test_broken_labels_and_shapes_are_still_hidden(text, hidden):
    out = mask(text)
    assert hidden not in out and "[" in out


def test_birth_year_is_kept_and_spacing_after_birthdate_stays():
    assert mask("생년월일 1990.01.01 생년 1955년생") == "생년월일 [생년월일] 생년 1955년생"
    assert mask("연락처 (02) 123-4567 끝") == "연락처 [전화번호] 끝"  # 괄호만 남지 않음


def test_labels_next_to_drug_numbers_do_not_eat_the_drug_line():
    text = "주민등록번호 900101-1234567 노바스크정5밀리그램 1 1 30"
    assert mask(text) == f"주민등록번호 {RRN} 노바스크정5밀리그램 1 1 30"


# ── 이름 보강 (10/15): 라벨이 깨졌거나 없는 이름 ──────────────────────────────────────────────────────

HEADER = "환자 성명 [이름] 전화번호 [전화번호] "  # 이름 근처에 신호(환자 · 성명 · 전화번호)가 있는 머리말


@pytest.mark.parametrize(
    "text, hidden",
    [
        ("환자 성멍 홍길동 전화번호 02-000-0000", "홍길동"),  # OCR이 '성명'을 잘못 읽음
        ("환자 성병 홍길동 전화번호 02-000-0000", "홍길동"),
        ("성멍 홍길동", "홍길동"),  # 신호가 깨진 라벨 하나뿐이어도 가림
        ("환자 홍길동 전화번호 02-000-0000", "홍길동"),  # 성명 라벨이 없음
        ("홍길동 성명 전화번호 02-000-0000", "홍길동"),  # 이름이 라벨 앞에 읽힘
        ("홍길동 900101-1234567", "홍길동"),  # 주민번호 옆
        ("홍길동 님 귀하", "홍길동"),
        ("홍길동님께 복약 안내", "홍길동"),
        ("홍길동씨", "홍길동"),
        ("환자명 홍길동", "홍길동"),
        ("환자명 이솔", "이솔"),  # 라벨이 분명하면 두 글자 이름도 가림
        ("수진자 김철수", "김철수"),
        ("보호자 김철수 연락처 010-1234-5678", "김철수"),
        ("조제약사 박약사", "박약사"),
        ("약사 성명 최약사", "최약사"),
        ("복약안내 남궁민수 님", "남궁민수"),  # 복성
        ("성명 전화영 전화번호 02-000-0000", "전화영"),  # 이름이 라벨 낱말(전화)로 시작해도 가림
        ("성명 사용광 생년 1955년생", "사용광"),
        ("이름 주소누", "주소누"),
        ("성명 교부솔", "교부솔"),  # 성씨 목록에 없는 이름이 라벨 글자(교부)로 시작해도 라벨 뒤라서 가림
        ("홍길동 test@example.com", "홍길동"),  # 가려진 이메일 표시도 신호
    ],
)
def test_names_without_a_clean_label_are_hidden_when_near_a_patient_signal(text, hidden):
    out = mask(text)
    assert hidden not in out and NAME in out
    assert mask(out) == out  # 다시 적용해도 같음


@pytest.mark.parametrize(
    "text, kept",
    [
        (HEADER + "주사액 1 1 30", "주사액"),  # 이름 모양인 의학 낱말
        (HEADER + "서방정 1 1 30", "서방정"),
        (HEADER + "마약류 처방", "마약류"),
        ("연락처 (02) 123-4567 끝", "연락처"),  # 라벨 낱말이 이름 모양
        ("이메일 test@example.com 끝", "이메일"),
        (HEADER + "전에는 복용하지 마세요", "전에는"),  # 조사로 끝나는 낱말
        (HEADER + "주의할 점", "주의할"),
        ("의료기관 명칭 서울행복내과의원 전화번호 02-000-0000", "서울행복내과의원"),  # 병원 이름은 남김
        # 성씨로 시작하는 병원 이름 (다섯 글자 한 낱말이라 이름 모양이 아님)
        ("김내과의원 전화번호 02-000-0000", "김내과의원"),
        ("이상반응 안전성 확인 필요", "안전성"),  # 환자 신호가 없는 의학 글은 건드리지 않음
        ("고혈압 당뇨병 신장애 소아용 성인용", "고혈압"),
        (
            "환자 성명 [이름] 노바스크정5밀리그램 1 1 30 아스피린프로텍트정100밀리그램 1 3 7",
            "아스피린프로텍트정100밀리그램",
        ),
    ],
)
def test_medical_and_form_words_that_look_like_names_are_kept(text, kept):
    out = mask(text)
    assert kept in out
    assert out.count(NAME) == text.count(NAME)  # 새로 이름으로 가려진 것이 없음
    assert mask(out) == out


def test_a_name_far_from_any_patient_signal_is_left_alone_and_two_letter_names_need_a_label():
    # 한계를 그대로 적어 둔다: 신호에서 멀리 떨어진 이름 · 라벨 없는 두 글자 이름은 못 가린다 (docs/design/ocr_mask.md)
    far = "환자 하나 둘 셋 넷 다섯 홍길동"
    assert "홍길동" in mask(far)
    assert "이솔" in mask("환자 가나 이솔")  # 신호에서 두 칸 떨어진 두 글자 이름
    assert "이솔" in mask("약국 이솔 접수")  # 신호가 없는 두 글자 이름


@pytest.mark.parametrize(
    "text",
    [
        "환자 이솔 전화번호 02-000-0000",  # 신호 바로 옆
        "환자 성멍 이솔",
        "이솔 [주민번호]",
        "이솔님 안녕하세요",
        "이솔씨 안녕하세요",
        "보호자 이솔",
        "조제약사 박솔",
    ],
)
def test_two_letter_names_right_next_to_a_signal_are_hidden(text):
    out = mask(text)
    assert "이솔" not in out and "박솔" not in out
    assert mask(out) == out


@pytest.mark.parametrize(
    ("text", "hidden"),
    [
        ("환자명:이솔 접수", "이솔"),
        ("수진자:이솔", "이솔"),
        ("보호자:김철수 접수", "김철수"),
        ("조제약사:박약사 확인", "박약사"),
    ],
)
def test_names_glued_to_their_label_with_a_colon_are_hidden(text, hidden):
    # 라벨과 이름이 한 덩어리로 읽히면 낱말 단위 신호로는 못 잡는다 → 라벨 규칙이 담당
    assert hidden not in mask(text)


def test_a_word_ending_in_ssi_is_not_a_name_plus_ssi():
    assert "지씨씨" in mask("환자 알부민 지씨씨 주")  # 제조사 이름 (지씨 + 씨로 읽히면 안 됨)


def test_two_letter_medical_and_form_words_next_to_a_signal_are_kept():
    for word in ("서명", "조제", "고객", "선생"):
        assert "[이름]" not in mask(f"환자 {word} 전화번호"), word


def test_name_masking_does_not_change_existing_results_and_stays_idempotent():
    text = sample_text() + " 보호자 김철수 홍길동 님 주민등록번호 900101-1234567"
    once = mask(text)
    assert "김철수" not in once and "홍길동" not in once and "김의사" not in once
    assert mask(once) == once
    assert NAME in once and "가나다내과의원" in once


def test_stopwords_file_is_loaded():
    from app.services.ocr import mask as mask_module

    assert len(mask_module._STOP) > 500 and "주사액" in mask_module._STOP and "서방정" in mask_module._STOP


def test_masking_a_name_never_creates_a_new_signal_for_the_next_run():
    # 첫 번째 적용에서 가려진 이름이 두 번째 적용에서 다른 낱말을 가리는 신호가 되면 안 된다 (여러 번 실행해도 같은 결과)
    text = "환자 홍길동 가 나 김철수"  # 김철수는 '환자'에서 4칸, 가려진 홍길동에서 3칸
    once = mask(text)
    assert "홍길동" not in once and "김철수" in once
    assert mask(once) == once


# 실제 처방전 사진 9장(10/15)의 CLOVA 결과에서 새던 모양들 (이름은 지어낸 것)
@pytest.mark.parametrize(
    ("text", "hidden"),
    [
        ("환 자 성 명 홍 길 동 팩스번호 02-123", "홍 길 동"),  # OCR이 이름 글자 사이에 공백을 넣음
        ("피보험자 : 김 영 희 ①의료보험", "김 영 희"),
        ("처방 의료인의 성 명 박 형 구 (인) 면허번호", "박 형 구"),
        ("조제약사 성명 (서명 또는 날인) 최민수 조 제 량", "최민수"),  # 성명 뒤에 괄호가 낌
        ("성 명 (인) 정 우 성 조제일수", "정 우 성"),
    ],
)
def test_names_the_real_prescriptions_leaked_are_hidden(text, hidden):
    out = mask(text)
    assert hidden not in out
    assert "[이름]" in out
    assert mask(out) == out


@pytest.mark.parametrize(
    "text",
    [
        "환 자 성 명 조 제 일 자 투 약 일 수 2024-05",  # 이름 칸이 비어 다음 칸 이름이 이어짐
        "전화 번 호 성 명 기 팩 스 번 호 환 자",
        "성 명 처 방 전 이 하 여 백",
        "요양기관기호 : 12345678 교부 연월일 ⑧·미 번호 2022년 12월 1일",
        "환 자 성 명 팩 스 번 호 2024-05",  # 성씨로 시작하지 않는 글자 줄은 이름이 아님
        "조제약사 성명 (서명 또는 날인) 조 제 량 (조제일수)",
    ],
)
def test_empty_name_boxes_followed_by_other_labels_are_not_hidden(text):
    assert "[이름]" not in mask(text)


# 실제 처방전 3장(s1~s3, 10/15)의 CLOVA 결과에서 새던 모양 (이름 · 번호는 지어낸 것)
@pytest.mark.parametrize(
    ("text", "hidden"),
    [
        ("보 험 보험 주 치 의 김외과 / 외과 용량 횟수", "김외과"),  # OCR이 라벨 글자마다 공백을 넣음
        ("주치의 : 박솔 접수", "박솔"),
        ("담당의사 최민수 확인", "최민수"),
        ("진료의 이솔 접수", "이솔"),
    ],
)
def test_attending_doctor_names_are_hidden(text, hidden):
    out = mask(text)
    assert hidden not in out and "[이름]" in out
    assert mask(out) == out


def test_attending_doctor_label_alone_does_not_hide_the_next_word():
    assert "[이름]" not in mask("주치의 확인 필요")


@pytest.mark.parametrize(
    ("text", "number"),
    [
        ("이 름 김환자 등록번호 06071226 주민번호 xxxxxx", "06071226"),
        ("병록번호: 12345678 요양기관기호:", "12345678"),
        ("차트번호 0012-345 환자", "0012-345"),
    ],
)
def test_hospital_registration_numbers_are_hidden(text, number):
    out = mask(text)
    assert number not in out and "[등록번호]" in out
    assert mask(out) == out


def test_registration_number_rule_leaves_resident_numbers_and_empty_labels_alone():
    assert "[등록번호]" not in mask("주민등록번호 900101-1234567")
    assert "[등록번호]" not in mask("주민등록 번호 871014-6")
    assert mask("병록번호: 요양기관기호:") == "병록번호: 요양기관기호:"  # 번호가 비어 있음


def test_resident_number_labels_are_never_taken_for_registration_number_labels():
    assert "[등록번호]" not in mask("주민등록번호: 12345")  # 주민등록번호의 "등록번호"만 따로 보지 않음
    assert "[등록번호]" not in mask("주민등록 번호 87101")


def test_the_attending_doctor_label_itself_is_not_taken_for_a_name():
    assert "주치의" in mask("환자 주치의 확인")


def test_a_masked_registration_number_is_a_signal_for_a_name_next_to_it():
    assert "이솔" not in mask("등록번호 06071226 이솔 접수")
