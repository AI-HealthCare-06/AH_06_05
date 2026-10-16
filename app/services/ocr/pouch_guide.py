"""약봉투 약 카드에 약국이 인쇄한 복약 안내 문구 읽기 (10/15)

카드형 약봉투(p1 · p3)는 약마다 이름 · 성분 줄 오른쪽에 "쪼개지 마세요", "위장장애 주의" 같은 짧은 표시와
"식사와 함께 1일 1회 복용하세요."처럼 완결된 안내 문장이 적혀 있다. 이 글자를 약 줄(`Row.guide`)에 모아 둔다.
(`drug_guides`에는 약별 주의 문구가 없다 — `docs/design/ocr_pill_bag.md`)

읽는 방법
1. 약 카드 칸: 이름 줄 바로 위(글자 높이 1배)부터 다음 이름 줄 바로 위까지. 마지막 약은 표의 끝(숫자 칸이 끝나는 곳)까지.
2. 왼쪽 열(이름 · "[분류]" · 성분 줄)은 제외한다: 왼쪽 끝에서 시작해 바짝 붙은(간격 ≤ 글자 높이 0.7배) 낱말을 오른쪽으로 이어 붙인 것.
   남은 한글 낱말이 안내 글자다. 숫자 칸 · 영수증 띠는 아예 이 함수에 들어오지 않는다 (호출하는 쪽이 이름 칸 왼쪽만 넘긴다).
3. 줄로 묶고(세로 가운데 차이 ≤ 글자 높이 0.5배), 한 줄 안에서 글자 높이의 0.6배 넘게 떨어진 곳에서 조각으로 나눈다.
   - 한 줄이 둘 이상의 조각이거나, 카드 맨 위 줄이 짧은(12자 이하) 한 조각이면 **표시**(chip)다: 조각마다 하나 ("쪼개지 마세요" · "씹지 마세요" · "위장장애 주의").
   - 그 밖의 줄은 **문장**이다. 줄을 이어 붙이고 "세요 · 어요 · 해요 · 니다 · 십시오"처럼 서술어 어미로 끝나는 낱말(뒤에 . ! ?가 와도)이나 . ! ?로 끝나는 낱말에서 끊는다. ("생리과다" · "필요" 같은 명사의 끝 글자는 끝맺음이 아니다)
     끝맺음이 없는 나머지 조각은 버린다 (잘린 문장을 안내로 보여 주지 않는다).
4. 글자 확실도: 표시 · 문장마다 평균 0.8 이상, 가장 낮은 낱말 0.6 이상일 때만 남긴다 (샘플 p1 · p3 · p4에서 정한 값이고 근거가 그보다 많지는 않다).
   확실하지 않은 글자가 섞인 안내는 보여 주지 않는 쪽이 낫다 — 잘못 읽힌 복약 안내가 사실처럼 보이면 안 된다.

저장하는 쪽(`prescriptions.save_read`)이 `mask()`를 적용한다. 영수증 띠를 저장하지 않는 것은 이 함수에 넘기는 범위로 정해진다 (`pouch.parse_pouch`).
"""

import re
import statistics
from collections.abc import Callable
from typing import Any

Box = tuple[float, float, float, float]
Item = tuple[dict[str, Any], Box]

_HANGUL = re.compile(r"[가-힣]")
_ENDING = re.compile(
    r"(?:세요|어요|아요|해요|지요|네요|니다|십시오|십시요)[.!?]?$|[.!?]$"
)  # 문장 끝 낱말. "생리과다" · "필요"처럼 명사가 요 · 다로 끝나는 것은 끝맺음이 아니다
# 왼쪽 열 낱말을 이어 붙이는 간격 한도 (글자 높이 배). 이름 · 성분 낱말 사이는 0~2px, 이름과 안내 글자 사이는 18px 이상
_CHAIN_GAP = 0.7
# 한 줄을 조각으로 가르는 간격 (글자 높이 배). 실측: 표시 사이 15px(높이 18의 0.83배), 문장 낱말 사이 0~5px
_CHIP_SPLIT = 0.6
_SAME_LINE = 0.5
# 표시 한 조각의 최대 글자 수 (공백 제외)
_CHIP_MAX = 12
MIN_MEAN = 0.8
MIN_EACH = 0.6
MAX_PER_DRUG = 10
MAX_LEN = 200


def _core(text: str) -> str:
    return re.sub(r"\s", "", text)


def _left_tokens(zone: list[Item], h: float) -> set[int]:
    """왼쪽 열(이름 · 분류 · 성분 줄)의 낱말 — 왼쪽 끝 한글 낱말에서 시작해 바짝 붙은 오른쪽 낱말을 이어 붙인 것"""
    cand = [(f, b) for f, b in zone if _HANGUL.search(f["inferText"])]
    if not cand:
        return set()
    edge = min(b[0] for _, b in cand) + 2 * h
    left = {id(f): b for f, b in cand if b[0] <= edge}
    grew = True
    while grew:
        grew = False
        for f, b in cand:
            if id(f) in left:
                continue
            for lb in left.values():
                if -0.5 * h <= b[0] - lb[2] <= _CHAIN_GAP * h and min(b[3], lb[3]) - max(b[1], lb[1]) >= 0.5 * min(
                    b[3] - b[1], lb[3] - lb[1]
                ):
                    left[id(f)] = b
                    grew = True
                    break
    return set(left)


def _lines(tokens: list[tuple[dict[str, Any], Box]], hm: float) -> list[list[tuple[dict[str, Any], Box]]]:
    ordered = sorted(tokens, key=lambda t: (t[1][1] + t[1][3]) / 2)
    lines: list[list[tuple[dict[str, Any], Box]]] = []
    for f, b in ordered:
        cy = (b[1] + b[3]) / 2
        if lines and abs(statistics.mean((x[1][1] + x[1][3]) / 2 for x in lines[-1]) - cy) <= _SAME_LINE * hm:
            lines[-1].append((f, b))
        else:
            lines.append([(f, b)])
    return [sorted(line, key=lambda t: t[1][0]) for line in lines]


def _segments(line: list[tuple[dict[str, Any], Box]], hm: float) -> list[list[tuple[dict[str, Any], Box]]]:
    segs = [[line[0]]]
    for t in line[1:]:
        if t[1][0] - segs[-1][-1][1][2] >= _CHIP_SPLIT * hm:
            segs.append([t])
        else:
            segs[-1].append(t)
    return segs


def _confident(words: list[tuple[str, float]]) -> bool:
    confs = [c for _, c in words]
    return bool(confs) and statistics.mean(confs) >= MIN_MEAN and min(confs) >= MIN_EACH


Words = list[tuple[str, float]]  # (낱말, 글자 확실도)


def _feed(pending: Words, seg: Words, emit: Callable[[Words], None]) -> Words:
    """문장 낱말을 이어 붙이다가 끝맺음 낱말에서 내보낸다. 끝맺지 못한 나머지를 돌려준다"""
    for word, conf in seg:
        pending.append((word, conf))
        if _ENDING.search(word):
            emit(pending)
            pending = []
    return pending


def _units(lines: list[list[tuple[dict[str, Any], Box]]], hm: float) -> list[str]:
    out: list[str] = []

    def emit(words: Words) -> None:
        text = " ".join(w for w, _ in words).strip()
        if 3 <= len(_core(text)) <= MAX_LEN and _confident(words) and text not in out:
            out.append(text)

    pending: Words = []  # 아직 끝맺지 못한 문장의 낱말
    for i, line in enumerate(lines):
        segs = [
            [(f["inferText"].strip(), float(f.get("inferConfidence", 1.0))) for f, _ in s] for s in _segments(line, hm)
        ]
        first_tag = (
            i == 0
            and len(segs) == 1
            and len(_core("".join(w for w, _ in segs[0]))) <= _CHIP_MAX
            and not any(_ENDING.search(w) for w, _ in segs[0])  # 끝맺음 낱말이 하나라도 있으면 문장이다
        )
        if len(segs) == 1 and not first_tag:
            pending = _feed(pending, segs[0], emit)
            continue
        pending = []  # 표시 줄 앞의 끝맺지 못한 조각은 버린다
        for seg in segs:
            if len(_core("".join(w for w, _ in seg))) <= _CHIP_MAX:
                emit(seg)  # 짧은 조각은 표시
            else:
                pending = _feed(pending, seg, emit)  # 긴 조각은 문장
    return out[:MAX_PER_DRUG]


def read_guidance(zone: list[Item], name_ys: list[float], h: float, end: float) -> list[list[str]]:
    """약마다 안내 표시 · 문장 목록 (이름 줄 높이 목록과 같은 순서). zone: 이름 칸(숫자 칸 왼쪽)의 낱말들, end: 표의 끝 높이"""
    if not name_ys or not zone:
        return [[] for _ in name_ys]
    hm = statistics.median(b[3] - b[1] for _, b in zone)
    left = _left_tokens(zone, h)
    rest = [(f, b) for f, b in zone if id(f) not in left and _HANGUL.search(f["inferText"])]
    out: list[list[str]] = []
    for i, cy in enumerate(name_ys):
        lo = cy - hm
        hi = name_ys[i + 1] - hm if i + 1 < len(name_ys) else end
        band = [(f, b) for f, b in rest if lo <= (b[1] + b[3]) / 2 < hi]
        out.append(_units(_lines(band, hm), hm) if band else [])
    return out
