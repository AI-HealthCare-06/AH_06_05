"""OCR 원문에서 개인을 알아볼 수 있는 정보를 가린 뒤 저장한다 (수인님 결정 10/14: 원문은 나중에 쓰되 가려서 저장)

가리는 것: 주민(외국인)등록번호 · 전화번호 · 환자 성명 · 처방 의료인 성명 · 면허번호 · 요양기관기호 · 보험증 번호 · 이메일
남기는 것: 의료기관 명칭 · 생년(년도만) · 교부일 · 질병분류기호 · 약 이름과 복용 숫자 — 챗봇 근거와 다시 분석에 필요한 내용

규칙(정규식)으로 가리므로 처방전 양식 밖에 적힌 이름 같은 것은 못 가린다. 한계는 docs/design/ocr_mask.md에 적었다.
같은 글자에 다시 적용해도 결과가 같다 (이미 가린 글자는 건드리지 않음).
"""

import re

NAME = "[이름]"
RRN = "[주민번호]"
PHONE = "[전화번호]"
LICENSE = "[면허번호]"
INSTITUTION = "[기관기호]"
INSURANCE = "[보험번호]"
EMAIL = "[이메일]"

_MARK = r"[\-–‐]"  # 하이픈 · 엔 대시
_HIDDEN = r"[*●○ⅹXx]"  # 양식에 이미 가려져 인쇄된 자리

# 라벨 뒤에 오는 한글 이름 (2~5자). 다음 라벨 낱말을 이름으로 오인하지 않도록 제외
_LABELS = "성명|이름|질병|분류|면허|전화|처방|의약|교부|환자|생년|의료|기관|명칭|번호|종류|사용|용법|주소"
_NAME_VALUE = rf"(?!(?:{_LABELS}))[가-힣]{{2,5}}(?![가-힣])"

_RULES: list[tuple[re.Pattern[str], str]] = [
    # 주민등록번호 900101-1234567 · 900101-1****** · 900101-1 · 붙여 쓴 13자리
    (re.compile(rf"(?<!\d)\d{{6}}\s*{_MARK}\s*[1-8*●○ⅹXx][\d*●○ⅹXx]{{0,6}}(?!\d)"), RRN),
    (re.compile(r"(?<!\d)\d{6}[1-8]\d{6}(?!\d)"), RRN),
    # 전화번호 02-000-0000 · 010-1234-5678 · 붙여 쓴 휴대폰
    (re.compile(rf"(?<!\d)0\d{{1,2}}(?:\s*[-–‐.)]\s*|\s+)\d{{3,4}}(?:\s*{_MARK}\s*|\s+)\d{{4}}(?!\d)"), PHONE),
    (re.compile(r"(?<!\d)01[016789]\d{7,8}(?!\d)"), PHONE),
    (re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"), EMAIL),
]

# 라벨은 남기고 값만 가린다: (라벨, 값) → "라벨 [표시]"
_LABELED: list[tuple[re.Pattern[str], str]] = [
    # 환자 성명 · 처방 의료인 성명 ("성명 홍길동", "의료인 김의사", "의료인의 성명 김의사")
    (re.compile(rf"((?:성명|이름)\s*[:：]?\s*){_NAME_VALUE}"), NAME),
    (re.compile(rf"(의료인(?:의)?\s*(?:성명|이름)?\s*[:：]?\s*){_NAME_VALUE}"), NAME),
    (re.compile(r"(면허\s*번호\s*[:：]?\s*)제?\s*\d[\d\-]*\s*호?"), LICENSE),
    (re.compile(r"(요양\s*기관\s*기호\s*[:：]?\s*)\d{6,10}"), INSTITUTION),
    (re.compile(r"((?:보험증|증)\s*번호\s*[:：]?\s*)[\w\-]{5,}"), INSURANCE),
]


def mask(text: str) -> str:
    for pattern, mark in _RULES:
        text = pattern.sub(mark, text)
    for pattern, mark in _LABELED:
        text = pattern.sub(lambda m, mark=mark: m[1] + mark, text)  # type: ignore[misc]
    return text
