"""질병분류기호 보정 — OCR이 잘못 읽은 코드(예: I10을 110으로)를 상병마스터(diseases)로 바로잡기

규칙: 질병분류기호는 "영문자 1자 + 숫자 2자(+ 세부 코드)"이고 상병마스터에 있어야 한다.
 1) 마스터에 그대로 있으면 정상 (대문자 L · I는 그대로 믿는다)
 2) 닮은 글자로 바꾼 후보(숫자 1은 I · L, 소문자 l은 I · L, 0은 O ...)와 첫 글자가 빠진 후보를 모두 모은다
 3) 후보가 하나뿐일 때만 "보정", 둘 이상이면 "후보 여러 개"(사용자가 고름), 없으면 "모름"
"""

import re
from collections.abc import Container

L2D = {"I": "1", "L": "1", "O": "0", "S": "5", "B": "8", "Z": "2", "G": "6"}
D2L = {"1": ["I", "L"], "0": ["O"], "5": ["S"], "8": ["B"], "2": ["Z"], "6": ["G"], "4": ["A"]}

NORMAL, FIXED, MANY, UNKNOWN = "정상", "보정", "후보 여러 개", "모름"


def fix_one(tok: str, codes: Container[str]) -> tuple[str, str | list[str] | None]:
    raw = re.sub(r"[^0-9A-Za-z]", "", tok)
    s = raw.upper()
    if not s:
        return UNKNOWN, None
    lower_l = raw[0] == "l"
    if s in codes and not lower_l:
        return NORMAL, s
    heads = [s[0]]
    if s[0].isdigit() or lower_l:
        heads = (["I", "L"] if lower_l else D2L.get(s[0], [])) + ([s[0]] if s[0].isdigit() else [])
    mid = "".join(
        L2D.get(c, c) if c.isalpha() else c for c in s[1:]
    )  # 첫 글자 뒤는 모두 숫자 자리다 (M545를 M54S로 읽은 경우도 바로잡는다)
    swap: list[str] = []
    for h in heads:
        cand = h + mid
        if cand in codes and cand not in swap and (cand != s or lower_l):
            swap.append(cand)
    prepend: list[str] = []
    if s[0].isdigit() and 2 <= len(s) <= 4:
        prepend = [c for c in (chr(a) + s for a in range(65, 91)) if c in codes and c not in swap]
        prepend.sort(key=lambda c: (c[0] != "I", c))  # I는 가늘어서 빠지기 쉬워 먼저
    cands = swap + prepend
    if len(cands) == 1:
        return FIXED, cands[0]
    if cands:
        return MANY, cands
    return UNKNOWN, None


def fix_field(raw: str, codes: Container[str]) -> list[tuple[str, str, str | list[str] | None]]:
    """OCR 원문 문자열(예: "110,E11")을 나눠 각각 바로잡는다 → [(원문, 상태, 결과)]"""
    out = []
    for t in re.split(r"[,\s]+", raw.strip()):
        if t:
            st, v = fix_one(t, codes)
            out.append((t, st, v))
    return out
