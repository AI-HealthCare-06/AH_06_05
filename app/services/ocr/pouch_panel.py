"""약봉투 오른쪽 "약품명" 칸의 이름으로 영수증 칸의 잘린 · 잘못 읽힌 이름 바로잡기 (10/16 실물 약봉투)

약국 약봉투에는 약 이름이 두 곳에 있다. 왼쪽 영수증 칸은 글자가 작고 약국 프로그램이 10자쯤에서 잘라 인쇄해서
"펜크티정375밀리그램(아", "에이탈정(아세클로페낙)", "가스:므틴정5밀리그람(모"처럼 잘리거나 한 글자가 잘못 읽힌다.
오른쪽 복약안내 칸의 "약품명" 아래에는 같은 약 이름이 크게 적혀 있고 확실도도 높다 ("펜크라정375mg", "에어탈정", "가스모틴정5mg").
영수증 칸 이름이 믿기 어려울 때(못 찾음, 괄호가 닫히지 않음, 글자가 흐림)만 이 칸의 이름으로 바꾼다. 이미 잘 찾은 이름은 건드리지 않는다.

짝 찾기: 영수증 칸 이름의 괄호 앞(상표 + 함량)과 약품명 칸 낱말을 자모 3글자 조각 유사도로 비교한다 (matcher.trigrams).
- 함량 숫자가 같아야 한다 (펜크라정375와 펜크라정500은 다른 약).
- 유사도 0.5 이상이고 두 번째로 비슷한 낱말보다 0.2 이상 높아야 한다. 아니면 바꾸지 않는다 (엉뚱한 이름으로 바꾸는 것보다 두는 쪽이 안전).
"""

import re
from typing import Any

from app.services.drug_names import unify
from app.services.ocr.matcher import similarity, trigrams
from app.services.ocr.pouch import _box, _core

MIN_SIM = 0.5
MIN_GAP = 0.2
MIN_CONF = 0.8  # 약품명 칸 글자의 확실도 (이보다 흐리면 바꾸지 않는다)
_HANGUL = re.compile(r"[가-힣]")
_NUM = re.compile(r"\d+(?:\.\d+)?")


def panel_words(fields: list[dict[str, Any]]) -> list[tuple[str, float]]:
    """오른쪽 "약품명" 머리글 아래 칸의 낱말과 그 낱말 둘을 이은 것 (이름이 두 낱말로 쪼개져 읽히는 경우). (글자, 확실도)
    "약품명" 머리글이 "약품사진" 또는 "복약안내"와 한 줄에 있을 때만 그 칸으로 본다 (영수증 칸의 "약품명 투약량 횟수 일수"와 구분)"""
    heads = [(f, _box(f)) for f in fields if _core(f["inferText"]) == "약품명"]
    for f, b in heads:
        h = b[3] - b[1]
        cy = (b[1] + b[3]) / 2
        mates = [
            _core(g["inferText"]) for g in fields if g is not f and abs((_box(g)[1] + _box(g)[3]) / 2 - cy) <= 0.6 * h
        ]
        if not any("복약안내" in m or "약품사진" in m for m in mates):
            continue
        cx = (b[0] + b[2]) / 2
        col = [
            (g, _box(g))
            for g in fields
            if cx - 230 <= _box(g)[0] <= cx + 30
            and (_box(g)[1] + _box(g)[3]) / 2 > b[3]
            and _HANGUL.search(g["inferText"])
        ]
        col.sort(key=lambda t: ((t[1][1] + t[1][3]) / 2, t[1][0]))
        out: list[tuple[str, float]] = []
        for i, (g, gb) in enumerate(col):
            conf = float(g.get("inferConfidence", 1.0))
            out.append((_core(g["inferText"]), conf))
            if i + 1 < len(col):
                n, nb = col[i + 1]
                if abs((nb[1] + nb[3]) / 2 - (gb[1] + gb[3]) / 2) <= 0.5 * (gb[3] - gb[1]):
                    out.append(
                        (_core(g["inferText"]) + _core(n["inferText"]), min(conf, float(n.get("inferConfidence", 1.0))))
                    )
        return out
    return []


def refine(name: str, words: list[tuple[str, float]]) -> str | None:
    """영수증 칸 이름에 짝이 되는 약품명 칸 이름. 확실한 짝이 없으면 None"""
    head = name.split("(")[0]
    if not words or not _HANGUL.search(head):
        return None
    q = trigrams(unify(head))
    nums = _NUM.findall(head)
    scored = sorted(
        (
            (similarity(q, trigrams(unify(w.split("(")[0]))), w)
            for w, conf in words
            if conf >= MIN_CONF and _NUM.findall(w.split("(")[0]) == nums
        ),
        reverse=True,
    )
    if not scored or scored[0][0] < MIN_SIM:
        return None
    if len(scored) > 1 and scored[0][0] - scored[1][0] < MIN_GAP:
        return None
    return scored[0][1]
