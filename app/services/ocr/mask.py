"""OCR 원문에서 개인을 알아볼 수 있는 정보를 가린 뒤 저장한다 (수인님 결정 10/14: 원문은 나중에 쓰되 가려서 저장)

가리는 것: 주민(외국인)등록번호 · 전화번호 · 환자 성명 · 처방 의료인 성명 · 면허번호 · 요양기관기호 · 보험증 번호 · 이메일 · 생년월일(전체)
남기는 것: 의료기관 명칭 · 생년(년도만) · 교부일 · 질병분류기호 · 약 이름과 복용 숫자 — 챗봇 근거와 다시 분석에 필요한 내용

이름은 글자만 봐서는 이름인지 알 수 없어서 세 겹으로 가린다 (10/15 보강):
① 라벨 바로 뒤 — 성명 · 이름 · 의료인 · 환자명 · 수진자 · 보호자 · 약사 등 (이름 모양이 아니어도 가림: 성명 · 이름 · 의료인)
② 님 · 씨 · 귀하 바로 앞의 이름 모양 낱말
③ 라벨이 깨졌거나 없어도, 이름 모양(성씨 + 2글자) 낱말이 환자 · 성명 · 주민번호 · 전화번호 같은 신호 근처(앞뒤 3칸)에 있으면 가림
이름 모양인 의학 낱말(주사액, 서방정 등)은 mask_stopwords.txt로 거른다. 규칙으로 가리므로 못 가리는 경우가 남는다 — 한계는 docs/design/ocr_mask.md.
같은 글자에 다시 적용해도 결과가 같다 (이미 가린 글자는 건드리지 않음).
"""

import re
from bisect import bisect_right
from pathlib import Path

NAME = "[이름]"
RRN = "[주민번호]"
PHONE = "[전화번호]"
LICENSE = "[면허번호]"
INSTITUTION = "[기관기호]"
INSURANCE = "[보험번호]"
EMAIL = "[이메일]"
BIRTH = "[생년월일]"
REGNO = "[등록번호]"

_MARK = r"[\-–‐]"  # 하이픈 · 엔 대시
_HIDDEN = r"[*●○ⅹXx]"  # 양식에 이미 가려져 인쇄된 자리

# 라벨 뒤에 오는 한글 이름 (2~5자). 다음 라벨 낱말을 이름으로 오인하지 않도록 제외
_LABELS = "성명|이름|질병|분류|면허|전화|처방|의약|교부|환자|생년|의료|기관|명칭|번호|종류|사용|용법|주소"
_HIDE_RUN = r"[\d*●○ⅹXx][\d*●○ⅹXx\s\-–]{4,18}[\d*●○ⅹXx]"  # 숫자 · 가려진 자리가 이어진 덩어리
# 다음 라벨을 이름으로 오인하지 않는다: 라벨 낱말 그대로(전화) 이거나 라벨로 시작하는 긴 낱말(전화번호). 이름이 라벨 글자로 시작해도(전화영) 가린다
_NAME_VALUE = rf"(?!(?:{_LABELS})(?:[가-힣]{{2,}}|(?![가-힣])))[가-힣]{{2,5}}(?![가-힣])"

_RULES: list[tuple[re.Pattern[str], str]] = [
    # 주민등록번호 900101-1234567 · 900101-1****** · 900101-1 · 붙여 쓴 13자리
    (re.compile(rf"(?<!\d)\d{{6}}\s*{_MARK}\s*[1-8*●○ⅹXx][\d*●○ⅹXx]{{0,6}}(?!\d)"), RRN),
    (re.compile(r"(?<!\d)\d{6}[1-8]\d{6}(?!\d)"), RRN),
    # 전화번호 02-000-0000 · 010-1234-5678 · 붙여 쓴 휴대폰
    (re.compile(rf"(?<!\d)\(?0\d{{1,2}}(?:\s*[-–‐.)]\s*|\s+)\d{{3,4}}(?:\s*{_MARK}\s*|\s+)\d{{4}}(?!\d)"), PHONE),
    (re.compile(r"(?<!\d)01[016789]\d{7,8}(?!\d)"), PHONE),
    (re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"), EMAIL),
]

# 라벨은 남기고 값만 가린다: (라벨, 값) → "라벨 [표시]"
_LABELED: list[tuple[re.Pattern[str], str]] = [
    # 환자 성명 · 처방 의료인 성명 ("성명 홍길동", "의료인 김의사", "의료인의 성명 김의사")
    (re.compile(rf"((?:성\s*명|이\s*름)\s*[:：]?\s*){_NAME_VALUE}"), NAME),
    (re.compile(rf"(의\s*료\s*인(?:의)?\s*(?:성\s*명|이\s*름)?\s*[:：]?\s*){_NAME_VALUE}"), NAME),
    # 라벨 뒤의 값은 모양이 달라도 가린다 (OCR이 하이픈을 빠뜨리거나 숫자 사이에 공백을 넣은 경우)
    (re.compile(rf"(주민\s*(?:등록)?\s*번호\s*[:：]?\s*){_HIDE_RUN}"), RRN),
    (re.compile(rf"(외국인\s*등록\s*번호\s*[:：]?\s*){_HIDE_RUN}"), RRN),
    (
        re.compile(r"((?:전화\s*번호|휴대\s*(?:폰|전화)|핸드폰|연락처|팩스)\s*[:：]?\s*)\(?\d[\d\s\-–.()]{6,15}\d"),
        PHONE,
    ),
    (
        re.compile(
            r"(생년\s*월일\s*[:：]?\s*)(?:\d{4}\s*[.\-/년]\s*\d{1,2}\s*[.\-/월]\s*\d{1,2}(?:\s*일)?|\d{6,8})(?!\d)"
        ),
        BIRTH,
    ),
    (re.compile(r"(면허\s*번호\s*[:：]?\s*)제?\s*\d[\d\-]*\s*호?"), LICENSE),
    (re.compile(r"(요양\s*기관\s*기호\s*[:：]?\s*)\d{6,10}"), INSTITUTION),
    (re.compile(r"((?:보험증|증)\s*번호\s*[:：]?\s*)[\w\-]{5,}"), INSURANCE),
    # 병원 환자 등록번호 · 병록번호 · 차트번호 (주민등록번호는 위 규칙이 먼저 처리: 앞에 "주민"이 붙으면 제외)
    (re.compile(r"((?<!주민)(?:병\s*록|차\s*트|환\s*자|등\s*록)\s*번\s*호\s*[:：]?\s*)\d[\d\-]{4,}"), REGNO),
]

# ── 이름 보강 (10/15) ─────────────────────────────────────────────────────────────────────────
# 흔한 성씨 (2015 인구주택총조사: 상위 30개 성씨가 86.1%, 1,000명 이상 153개가 99.8% — 이 목록이 그만큼 덮는지는 재지 않았다)
SURNAMES = "김이박최정강조윤장임한오서신권황안송류전홍고문양손배백허유남심노하곽성차주우구민나진지엄채원천방공현함변염여추도소석선설마길연위표명기반왕금옥육인맹제모탁국어은편용예경봉사부"
SURNAMES_2 = ("남궁", "황보", "제갈", "선우", "독고", "사공", "서문")
_N3 = rf"[{SURNAMES}][가-힣]{{2}}"
_N4 = rf"(?:{'|'.join(SURNAMES_2)})[가-힣]{{2}}"
_SHAPE = rf"(?:{_N4}|{_N3})"  # 이름 모양: 성씨 + 2글자 (복성은 4글자)
_SHAPE2 = rf"(?:{_SHAPE}|[{SURNAMES}][가-힣])"  # 라벨이 분명할 때는 외자 이름(성씨 + 1글자)도

_STOP_FILE = Path(__file__).with_name("mask_stopwords.txt")
# 이름 모양이지만 이름이 아닌 낱말: 양식 · 직책 · 의학 낱말 (+ 파일: 약 이름 · 제조사 · 질병명에서 뽑은 것 — scripts/gen_mask_stopwords.py)
_STOP = frozenset(
    "이메일 이용자 전문의 한의원 주사제 조제량 조제약 조제일 조제시 조제자 주사액 서방정 장용정 연질캡 전화번 의료인 수진자 조제기관 약사님 마약류 처방전 이하여백 조제내역 조제연월일 조제일수 처방의약품 투약일수 조제기관명 연월일 년월일 선생 고객 서명 조제 주사 용량 금액 전문 한방 진료 성별 연령 나이 유효 기간 국민 인쇄 방문 변경 구분 기호 방법 주민 연번".split()
) | frozenset(_STOP_FILE.read_text(encoding="utf-8").split() if _STOP_FILE.exists() else [])

# 이름 근처에 있는 신호: 이 낱말이나 가려진 번호 표시가 앞뒤 3칸 안에 있을 때만 "라벨 없는 이름 모양"을 가린다
_ANCHOR_WORDS = frozenset(
    "환자 성명 이름 환자명 수진자 수진자명 피보험자 보호자 대리인 수령인 약사 조제약사 조제자 의료인 처방의 성 명 님 씨 귀하 생년 생년월일 성별 주민등록번호 주민번호 전화번호 휴대폰 연락처 면허번호".split()
)
_STOP = _STOP | _ANCHOR_WORDS | frozenset(_LABELS.split("|"))  # 라벨 낱말(연락처 등)을 이름으로 오인하지 않음
# 가려진 번호 표시. NAME은 일부러 뺌 (가려진 이름이 다음 적용에서 신호가 되면 결과가 달라진다)
_ANCHOR_MARKS = (RRN, PHONE, BIRTH, LICENSE, EMAIL, INSTITUTION, INSURANCE, REGNO)
_GARBLED_LABEL = re.compile(r"성[명멍몀병영맹뎡]|이[름믐릅]")  # OCR이 라벨을 잘못 읽은 모양
_ANCHOR_WINDOW = 3
# 조사 · 어미로 끝나는 낱말(전에는 · 서버에 · 주의할 · 마세요)은 이름이 아니다. 이름 끝에는 거의 오지 않는 글자만 골랐다 (이 · 서 · 은 · 한 · 성 등 이름에 흔한 글자는 뺌)
_PARTICLE_END = "는을를에의할요"

# 라벨 뒤의 이름: 이름 모양일 때만 (라벨이 흔한 낱말이라 아무 낱말이나 가리면 안 됨)
_ROLE_NAME = re.compile(
    rf"((?:환자\s*명|환자\s*이름|수진자(?:\s*명)?|피보험자(?:\s*명)?|주\s*치\s*의(?:사)?|담\s*당\s*의(?:사)?|진\s*료\s*의|집\s*도\s*의)\s*[:：]?\s*)({_SHAPE2})(?![가-힣])"
)
_ROLE_NAME_3 = re.compile(
    rf"((?:보호자|대리인|수령인|조제\s*약사|약사|조제자|복약\s*지도(?:자|\s*약사)?)(?:\s*성\s*명)?\s*[:：]?\s*)({_SHAPE})(?![가-힣])"
)
# OCR이 이름 글자 사이에 공백을 넣은 경우 ("성 명 박 형 구", "피보험자 : 이 현 상") · 성명 뒤에 "(서명 또는 날인)"이 낀 경우
_SPACED = rf"[{SURNAMES}](?:[ \t][가-힣]){{1,3}}(?![가-힣])(?![ \t][가-힣](?![가-힣]))"  # 뒤에 한 글자 낱말이 또 오면 칸 이름(투 약 일 수)일 수 있어 가리지 않음
_SPACED_NAME = re.compile(
    rf"((?:성\s*명|이\s*름|환자\s*명|수진자(?:\s*명)?|피보험자(?:\s*명)?)\s*[:：]?\s*)(?<![가-힣])({_SPACED})"
)
_SIGNED_NAME = re.compile(
    rf"((?:성\s*명|이\s*름)\s*\(\s*(?:서\s*명\s*또는\s*날\s*인|서\s*명|인)\s*\)\s*[:：]?\s*)({_SHAPE}|{_SPACED})(?![가-힣])"
)

# 님 · 씨 · 귀하 앞
_HONORIFIC = re.compile(rf"(?<![가-힣\[])({_SHAPE}|[{SURNAMES}][가-힣](?<!씨))(?=\s*(?:님|씨(?![가-힣])|귀하))")
_CANDIDATE = re.compile(rf"(?<![가-힣\[])({_SHAPE})(?![가-힣\]])")
_CANDIDATE2 = re.compile(rf"(?<![가-힣\[])([{SURNAMES}][가-힣])(?![가-힣\]])")  # 두 글자 이름: 신호 바로 옆일 때만
_TOKEN = re.compile(r"\S+")


def _is_anchor(token: str) -> bool:
    if NAME in token:
        return False  # 가려진 이름 표시는 신호가 아니다: 표시의 글자(이름)가 신호 낱말과 같아 두 번째 적용 때 다른 낱말을 가리게 된다
    if any(mark in token for mark in _ANCHOR_MARKS):
        return True
    core = re.sub(r"^[^가-힣]+|[^가-힣]+$", "", token)
    return core in _ANCHOR_WORDS or bool(_GARBLED_LABEL.fullmatch(core))


def _hide_names_near_anchors(text: str) -> str:
    tokens = [(m.start(), m[0]) for m in _TOKEN.finditer(text)]
    starts = [s for s, _ in tokens]
    anchors = [i for i, (_, tok) in enumerate(tokens) if _is_anchor(tok)]
    if not anchors:
        return text
    spans: list[tuple[int, int]] = []
    for m in _CANDIDATE.finditer(text):
        if m[1] in _STOP or m[1][-1] in _PARTICLE_END:
            continue
        i = bisect_right(starts, m.start()) - 1
        if any(abs(a - i) <= _ANCHOR_WINDOW for a in anchors):
            spans.append((m.start(1), m.end(1)))
    for m in _CANDIDATE2.finditer(text):
        if m[1] in _STOP or m[1][-1] in _PARTICLE_END:
            continue
        i = bisect_right(starts, m.start()) - 1
        if any(abs(a - i) <= 1 for a in anchors):
            spans.append((m.start(1), m.end(1)))
    spans = sorted(set(spans))
    for start, end in reversed(spans):
        text = text[:start] + NAME + text[end:]
    return text


def mask(text: str) -> str:
    for pattern, mark in _RULES:
        text = pattern.sub(mark, text)
    for pattern, mark in _LABELED:
        text = pattern.sub(lambda m, mark=mark: m[1] + mark, text)  # type: ignore[misc]
    for role in (_ROLE_NAME, _ROLE_NAME_3):
        text = role.sub(lambda m: m[0] if m[2] in _STOP else m[1] + NAME, text)
    for spaced in (_SPACED_NAME, _SIGNED_NAME):
        text = spaced.sub(lambda m: m[0] if m[2].replace(" ", "") in _STOP else m[1] + NAME, text)
    text = _HONORIFIC.sub(lambda m: m[0] if m[1] in _STOP else NAME, text)
    return _hide_names_near_anchors(text)
