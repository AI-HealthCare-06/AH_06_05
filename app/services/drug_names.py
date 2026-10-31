"""약 이름 정규화 — 약제급여목록 이름과 OCR이 읽은 이름을 같은 모양으로 맞춤 (맛보기 #29)

예: "노바스크정5밀리그람(암로디핀베실산염)_(6.944mg/1정)" → "노바스크정5밀리그램(암로디핀베실산염)"
"""

import re
import unicodedata
from collections.abc import Iterable


def base_name(name: str) -> str:
    """규격 "_(6.944mg/1정)"을 떼고 공백을 없앰"""
    return re.sub(r"\s", "", name.split("_(")[0])


_PAIR = {"(": ")", "[": "]", "<": ">"}


def display_name(name: str) -> str:
    """화면에 보내는 이름. base_name에서 약제급여목록 제품명의 수출명부터 뒤를 뗌.
    이름 맞추기(base_name, normalize_name)는 DB의 item_name_norm과 맞아야 해서 그대로 둠 (10/29 배포 서버 스로펜).
    수출명 앞에 남는 [ < / , 와 "캄보디아" 같은 나라 이름은 짝이 안 맞는 여는 괄호부터 지움. 괄호 안 성분 뒤에 쉼표로
    수출명이 이어지면("파무정(프랄리독심염화물,수출명:…") 성분은 남기고 괄호를 닫음 (#152 리뷰, 원본 528개에서 깨지는 이름 0개)"""
    base = base_name(name)
    i = base.find("수출명")
    if i < 0:
        return base
    head = base[:i].rstrip()
    after_comma = head.endswith(",")
    head = head.rstrip(" /,:")
    opened: list[int] = []  # 아직 닫히지 않은 여는 괄호 자리
    for j, ch in enumerate(head):
        if ch in _PAIR:
            opened.append(j)
        elif opened and ch == _PAIR[head[opened[-1]]]:
            opened.pop()
    if opened and after_comma:
        head += "".join(_PAIR[head[j]] for j in reversed(opened))
    elif opened:
        head = head[: opened[0]].rstrip(" /,:")
    return head or base


def unify(name: str) -> str:
    """표기 통일: 밀리그람 · mg → 밀리그램 (통일 없이 하면 비슷한 다른 약을 1등으로 고름)"""
    # NFKC로 호환 문자를 먼저 푼다(㎎ → mg · ㎍ → μg · ㎖ → ml). 급여목록 이름 22,045개 중 234개가 이 문자를 쓰는데, 풀지 않으면 "500mg"로 읽은 약이
    # "500㎎" 이름과 글자가 달라 보여 다른 함량의 약이 더 높은 점수를 받는다 (10/15 점검에서 데파코트서방정500㎎ → 250mg로 확정되는 것을 발견)
    return unicodedata.normalize("NFKC", name).lower().replace("밀리그람", "밀리그램").replace("mg", "밀리그램")


# 처방전 약 이름 칸 끝(또는 앞)에 붙어 읽히는 제조사: "...(엘록시캄)제일약품(주)" · "...(나프타존)(주)한국팜비오-"
# 급여목록 제품명 22,045개 중 "(주)"가 들어간 이름은 0개라서 이 패턴으로 떼어도 진짜 이름이 지워지지 않는다 (10/14 확인)
# 앞에 ")" · "-" · 공백 같은 경계가 있을 때만 뗀다 ("넥실렌에스정제일약품(주)"처럼 이름에 붙어 있으면 어디까지가 이름인지 모르므로 이 규칙으로는 안 뗌)
_MAKER_TAIL = re.compile(r"(?<=[)\]\-–\s])(?:[가-힣A-Za-z&·]{2,15}\(주\)|\(주\)[가-힣A-Za-z&·]{2,15})[-–\s]*$")


def maker_pattern(makers: Iterable[str]) -> re.Pattern[str] | None:
    """급여목록의 제조사 이름(예: "제일약품(주)")으로 만든 꼬리 패턴 — 이름에 붙어 있어도 정확히 일치하면 뗄 수 있음.
    "(주)"가 없는 이름은 제품명 일부와 겹칠 수 있어 쓰지 않는다"""
    names = sorted({m.strip() for m in makers if m and "(주)" in m}, key=len, reverse=True)
    return re.compile(r"(?:" + "|".join(re.escape(n) for n in names) + r")[-–\s]*$") if names else None


def strip_maker(name: str, pattern: re.Pattern[str] | None = None) -> str:
    """OCR이 읽은 약 이름에서 제조사 꼬리와 앞뒤 줄표를 뗌 (약 이름 맞추기 전 정규식 정리)"""
    s = re.sub(r"^[-–·\s]+", "", name.strip())
    s = _MAKER_TAIL.sub("", s)
    if pattern is not None:
        s = pattern.sub("", s)
    return re.sub(r"[-–\s]+$", "", s)


def normalize_name(name: str) -> str:
    """NFKC로 호환 문자를 먼저 풀어 줌 (㎎ → mg · ㎖ → ml · 전각 괄호 → 반각). 그다음 규격 · 공백 · 표기 통일"""
    return unify(base_name(unicodedata.normalize("NFKC", name)))
