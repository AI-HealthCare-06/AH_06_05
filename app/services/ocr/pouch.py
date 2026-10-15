"""약봉투 표 읽기 — 처방전 표(table.py)와 머리글이 달라서 따로 읽는다 (10/15)

처방전은 "투약일수" 머리글을 기준으로 읽는다. 약봉투는 "투약량 · 횟수 · 일수"를 한 줄로 늘어놓은 표를 쓰거나(p1 · r2 · p3),
머리글 없이 "약 이름 + 숫자 3개"만 줄지어 있다(p4_2016). 처방전을 못 읽었을 때(`parse_table`이 None)만 이 함수를 부른다.

읽는 방법 (글자 순서가 아니라 위치로 읽는다 — CLOVA는 글자 목록 순서를 보장하지 않는다)
1. 같은 줄에서 왼쪽부터 "투약량 · 횟수 · 일수" 세 낱말이 모인 곳을 머리글로 본다. 없으면 이름 + 숫자 3칸 목록을 찾아(`_headerless_columns`)
   읽고 `Table.headerless`로 표시한다 (칸 순서는 추정이라 사용자가 확인).
2. 머리글(또는 목록) 아래의 글자만 본다. 숫자는 세 칸 위치 안의 것만, 이름은 투약량 칸 왼쪽의 것만 읽는다.
   그래서 오른쪽의 영수증 띠(이름 · 주소 · 승인번호)는 읽지 않는다.
3. 숫자 줄(카드)마다 이웃 줄과의 가운데선으로 구간(창)을 나누고, **구간의 맨 위 줄이 약 이름**이다 (글자 크기가 아니라 위치).
   구간의 맨 위 줄이 유독 작으면(앞 카드 안내 꼬리 등) 큰 글자 줄 중 맨 위를 이름으로 하되 `Row.unsure`로 표시해 사용자가 확인한다.
   이름은 왼쪽 끝 한글에서 시작하고 "["로 시작하지 않으며, 오른쪽에 바짝 붙은 같은 크기의 조각(함량 `10mg` · `5/100`)을 이어 붙인다.
   숫자 칸에서 읽은 낱말은 이름에 붙이지 않는다. 숫자 없는 약 줄은 글자 크기가 이름급이고 다른 이름과 카드 간격만큼 떨어져 있을 때만 더한다.
4. 숫자는 세 칸(가로 위치)으로 1회량 · 하루 횟수 · 총 일수에 나누고, 이름 줄 사이의 가운데선으로 칸을 나눠 이름에 붙인다.
5. 숫자가 하나도 읽히지 않은 줄이 표의 처음이나 끝에 있으면 표 바깥 글자(안내 문구 · 방문일 등)로 보고 버린다.
   표 가운데에서 숫자만 못 읽은 줄은 약일 수 있어서 남긴다 (사용자가 확인 · 입력).
6. 약 카드에 약국이 인쇄한 복약 안내는 `pouch_guide.read_guidance`가 약마다 읽는다 (`Row.guide`).

이름 끝이 "···"로 잘린 줄은 `Row.cut`으로 표시하고, 파이프라인이 자동 확정하지 않고 사용자가 고르게 한다.

한계: 샘플 4종으로 만든 규칙이다. 이름이 두 줄로 꺾이면 줄마다 약 하나로 읽힐 수 있다 (이 경우 숫자 칸 수와 약 줄 수가
달라서 `row_count_mismatch`가 켜진다). 약봉투에 적힌 날짜는 `dispensed_date`가 읽는다. 자세한 것은 `docs/design/ocr_pill_bag.md`.
"""

import re
import statistics
from datetime import date
from typing import Any

from app.services.ocr.pouch_guide import read_guidance
from app.services.ocr.table import _NUM, Row, Table, _merge_split_heads

_DOSE = re.compile(r"(?:투[약여])?량")
_TIMES = re.compile(r"(?:투[약여])?횟수")
_DAYS = re.compile(r"(?:투[약여])?일수")
_HANGUL = re.compile(r"[가-힣]")
_NAME_GAP = 1.2  # 이름 뒤에 이어 붙이는 조각과의 간격 한도 (머리글 글자 높이의 배수). 실측: 이름 뒤 함량은 0~6px, 이름 옆 안내 문장은 30px 이상
_SAME_SIZE = 0.7  # 이름 뒤에 이어 붙이는 조각(100mg 등)의 글자 높이가 이름 글자의 이 비율 이상일 때만 (실측 p1: 안내 문장 17~18 / 이름 24~29 = 0.75 이하, p3: 함량 "0.1%" 18 / 이름 20 = 0.9)
_NEAR_TALLEST = 0.9  # 구간 안에서 가장 큰 글자의 이 비율 이상인 줄 중 맨 위가 이름 (이름이 성분보다 약간만 커도, 숫자 없는 카드의 작은 줄이 섞여도 이름을 찾는다)
_TOP_LIKE = 0.8  # 구간 맨 위 줄의 글자 높이가 구간별 가장 큰 글자 높이의 중앙값의 이 비율 이상이면 약 이름으로 본다 (흔들려도 이름이 성분 줄에 밀리지 않게 글자 크기보다 위치를 우선)
_MIN_APART = 0.4  # 숫자 없는 약의 이름 줄은 다른 이름 줄과 카드 간격(구간 높이)의 이 비율 이상 떨어져야 한다 (같은 카드 안의 줄은 간격의 0.3배 이내)
_SEPARATE = 1.15  # 이름 줄 평균 글자 높이가 나머지 줄의 이 배수보다 클 때만, 숫자 없는 약 줄을 글자 크기로 가려낸다
_LEAD = re.compile(r"^[\s*·•]+")
_TAIL = re.compile(r"(?:[·.]{2,}|…)\s*$")  # "슈가메트서방정5/100···"처럼 잘린 이름의 끝
_DATE = re.compile(r"(\d{4})\s*[.\-/]\s*(\d{1,2})\s*[.\-/]\s*(\d{1,2})")
_LABEL = re.compile(r"조\s*제\s*일\s*자?\s*[:：]?\s*$")


def _box(f: dict[str, Any]) -> tuple[float, float, float, float]:
    v = f["boundingPoly"]["vertices"]
    xs = [p["x"] for p in v]
    ys = [p["y"] for p in v]
    return min(xs), min(ys), max(xs), max(ys)


def _core(text: str) -> str:
    return re.sub(r"\s", "", text)


def _find_header(fields: list[dict[str, Any]]) -> tuple[int, int, int] | None:
    """같은 줄에 왼쪽부터 투약량 · 횟수 · 일수가 나란히 있는 곳 (낱말 번호). 후보가 여럿이면 줄이 가장 가지런한 것"""

    def words(rx: re.Pattern[str]) -> list[int]:
        return [k for k, f in enumerate(fields) if rx.fullmatch(_core(f["inferText"]))]

    def mid(k: int) -> tuple[float, float, float]:
        b = _box(fields[k])
        return (b[0] + b[2]) / 2, (b[1] + b[3]) / 2, max(b[3] - b[1], 1.0)

    best: tuple[float, int, int, int] | None = None
    for n in words(_DAYS):
        xn, yn, hn = mid(n)
        for t in words(_TIMES):
            xt, yt, ht = mid(t)
            if not (0 < xn - xt <= 15 * hn and abs(yn - yt) <= max(hn, ht)):
                continue
            for d in words(_DOSE):
                xd, yd, hd = mid(d)
                if not (0 < xt - xd <= 15 * hn and abs(yt - yd) <= max(ht, hd)):
                    continue
                spread = max(yd, yt, yn) - min(yd, yt, yn)
                if best is None or spread < best[0]:
                    best = (spread, d, t, n)
    return None if best is None else best[1:]


Box = tuple[float, float, float, float]
Item = tuple[dict[str, Any], Box]


def _row_centers(nums: list[tuple[int, float, float]], h: float) -> list[float]:
    """세로로 가까운 숫자들을 한 줄(카드)로 묶은 줄 가운데 높이들. 한 카드의 세 숫자는 거의 같은 높이에 있다"""
    ys = sorted(n[1] for n in nums)
    groups = [[ys[0]]]
    for y in ys[1:]:
        if y - groups[-1][-1] > 0.5 * h:
            groups.append([y])
        else:
            groups[-1].append(y)
    return [statistics.mean(g) for g in groups]


def _windows(centers: list[float], h: float) -> list[tuple[float, float]]:
    """줄(카드)마다 맡는 높이 구간: 이웃한 줄 가운데의 중간선까지. 맨 위 · 아래 줄은 이웃과의 간격의 절반만큼.
    줄이 하나뿐이면 간격을 알 수 없어서 머리글 글자 높이의 3.5배만큼 위 · 아래로 본다 (실측 카드 높이의 절반은 약 2.5배)"""
    if len(centers) < 2:
        return [(c - 3.5 * h, c + 3.5 * h) for c in centers]
    bounds = [(a + b) / 2 for a, b in zip(centers, centers[1:], strict=False)]
    first = centers[0] - (centers[1] - centers[0]) / 2
    last = centers[-1] + (centers[-1] - centers[-2]) / 2
    edges = [first, *bounds, last]
    return list(zip(edges, edges[1:], strict=False))


_STRENGTH = re.compile(
    r"^\d[\d.,/]*(?:mg|㎎|g|mL|ml|㎖|%|mcg|μg|㎍|IU)?(?:/[\d.,]+(?:mg|㎎|g|mL|ml|%)?)?$", re.I
)  # 함량 조각: "10mg" · "5/100" · "0.1%"


def _joins(g: dict[str, Any], c: Box, first: Box, last: Box, height: float, h: float) -> bool:
    """이름 뒤에 붙을 오른쪽 조각인가. 보통 조각은 바로 오른쪽에서 이름만큼 크고 세로로 겹쳐야 한다(안내 문장은 작거나 떨어져 있어 붙지 않는다).
    숫자로 시작하는 함량 조각("10mg")은 이름 글자가 아니면 안내 문장일 수 없어서, 사진이 흔들려 크기 · 겹침이 어긋나도 붙도록 조건을 느슨하게 본다"""
    if _STRENGTH.match(_core(g["inferText"])):
        gap, size, overlap = 2.0 * h, 0.4, 0.25
    else:
        gap, size, overlap = _NAME_GAP * h, _SAME_SIZE, 0.5
    return (
        -0.5 * h <= c[0] - last[2] <= gap  # 바로 오른쪽, 가까이 (상자가 살짝 겹쳐도 됨)
        and c[3] - c[1] >= size * height  # 이름보다 작은 글자(안내 문장)는 붙이지 않는다
        and min(first[3], c[3]) - max(first[1], c[1]) >= overlap * min(height, c[3] - c[1])  # 세로로 겹친다
    )


def _left_lines(zone: list[Item], h: float) -> list[tuple[float, str, bool, float, list[float]]]:
    """이름 칸의 왼쪽 끝에서 시작하는 줄들: (줄 높이 위치, 글자, 끝이 잘렸는지, 글자 높이).
    왼쪽 끝의 한글 글자에서 시작해 오른쪽으로, 세로로 겹치고 가까운 같은 크기의 조각("100mg" · "5/100")을 이어 붙인다.
    이름 오른쪽의 안내 문장은 크기가 작거나 떨어져 있어 붙지 않고, "["로 시작하는 분류 줄과 약 사진 안의 글자("SW" · "10")는 시작이 되지 않는다"""
    cand = [(f, b) for f, b in zone if _HANGUL.search(f["inferText"])]
    if not cand:
        return []
    edge = (
        min(b[0] for _, b in cand) + 2 * h
    )  # 이름은 이름 칸 왼쪽 끝에서 시작한다 (오른쪽의 안내 문장은 이름이 아니다)
    starts = sorted(
        (t for t in cand if t[1][0] <= edge and not _core(t[0]["inferText"]).startswith(("[", "(", "{"))),
        key=lambda t: (t[1][1] + t[1][3]) / 2,
    )
    used: set[int] = set()
    out: list[tuple[float, str, bool, float, list[float]]] = []
    for f, b in starts:
        if id(f) in used:
            continue
        height = b[3] - b[1]
        kept = [(f, b)]
        while not _TAIL.search(kept[-1][0]["inferText"]):
            last = kept[-1][1]
            nxt = [
                (g, c)
                for g, c in zone
                if id(g) not in used
                and g is not f
                and all(g is not k[0] for k in kept)
                and _joins(g, c, b, last, height, h)
            ]
            if not nxt:
                break
            kept.append(min(nxt, key=lambda t: t[1][0]))
        used.update(id(g) for g, _ in kept)
        text = _LEAD.sub("", "".join(_core(g["inferText"]) for g, _ in kept))
        cut_end = bool(_TAIL.search(text))
        text = _TAIL.sub("", text).strip()
        if text:
            confs = [float(g["inferConfidence"]) for g, _ in kept if isinstance(g.get("inferConfidence"), int | float)]
            out.append(((b[1] + b[3]) / 2, text, cut_end, statistics.median(c[3] - c[1] for _, c in kept), confs))
    return out


def _names(
    zone: list[Item], h: float, windows: list[tuple[float, float]]
) -> list[tuple[float, str, bool, bool, list[float]]]:
    """약 이름 줄들: [(줄 높이 위치, 이름, 끝이 잘렸는지, 이름 줄이 불확실한지)].
    각 줄(카드)의 숫자가 맡은 구간 안에서, 가장 큰 글자에 가까운 줄 중 **맨 위 줄이 약 이름**이다. 카드형은 이름 아래에 성분 · 분류 · 안내가 오고, 한 줄형은 줄마다 구간이 하나다.
    (처음에는 글자 높이로 이름을 골랐는데, 실제 샘플 p3는 이름 19~22 · 성분 16~18로 차이가 작아 불안정했고 표 밖의 큰 광고 글자에도 흔들렸다)
    숫자를 하나도 못 읽은 약은 구간의 첫 줄이 아니어도, 이름 글자가 성분 글자보다 뚜렷이 클 때만 약으로 더한다."""
    lines = _left_lines(zone, h)
    if not lines or not windows:
        return []
    inside_of = [[i for i, ln in enumerate(lines) if lo <= ln[0] < hi] for lo, hi in windows]
    ref = (
        statistics.median(max(lines[i][3] for i in inside) for inside in inside_of if inside) if any(inside_of) else 0.0
    )
    first_of: set[int] = set()
    # 맨 위 줄이 이름 같지 않아 큰 글자 줄로 바꾼 구간: 글자 크기로 고른 것이라 사용자가 확인한다
    unsure: set[int] = set()
    for inside in inside_of:
        if not inside:
            continue
        top = min(inside, key=lambda i: lines[i][0])
        if lines[top][3] >= _TOP_LIKE * ref:
            first_of.add(
                top
            )  # 구간 맨 위 줄이 구간별 가장 큰 글자 높이(중앙값)와 비슷하면 그게 이름이다 (글자 크기 차이가 작아도 위치로 정한다)
            continue
        tallest = max(
            lines[i][3] for i in inside
        )  # 유독 작은 줄(앞 카드의 안내 문장 꼬리 등)이 맨 위면 큰 글자 줄 중 맨 위를 이름으로
        near = [i for i in inside if lines[i][3] >= _NEAR_TALLEST * tallest]
        pick = min(near, key=lambda i: lines[i][0])
        first_of.add(pick)
        unsure.add(pick)
    others = [ln[3] for i, ln in enumerate(lines) if i not in first_of]
    cut = float("inf")
    if first_of and others:
        mean_name = statistics.mean(lines[i][3] for i in first_of)
        mean_other = statistics.mean(others)
        if mean_name > _SEPARATE * mean_other:
            cut = (mean_name + mean_other) / 2
    lo_all, hi_all = windows[0][0], windows[-1][1]
    pitch = statistics.median(hi - lo for lo, hi in windows)
    firsts = [lines[i][0] for i in first_of]

    def extra(ln: tuple[float, str, bool, float, list[float]]) -> bool:
        # 숫자 없는 약의 이름: 크기가 이름급이고, 이미 정한 이름들과 카드 간격의 일정 비율 이상 떨어져 있어야 한다 (이름 바로 아래의 "[분류]" 줄이 흔들려 커 보여도 약이 되지 않게)
        return ln[3] >= cut and lo_all <= ln[0] < hi_all and all(abs(ln[0] - y) >= _MIN_APART * pitch for y in firsts)

    keep = [ln for i, ln in enumerate(lines) if i in first_of or extra(ln)]
    return [(ln[0], ln[1], ln[2], any(lines[i] is ln for i in unsure), ln[4]) for ln in keep]


def _attach(
    names: list[tuple[float, str, bool, bool, list[float]]],
    nums: list[tuple[int, float, float]],
    guides: list[list[str]],
) -> list[Row]:
    """이름 줄 사이의 가운데선으로 나눈 칸 안의 숫자를 그 약에 붙인다 (카드형은 숫자가 카드 가운데에 있다)"""
    rows: list[Row] = []
    for i, (cy, text, cut_end, unsure, confs) in enumerate(names):
        upper = (names[i - 1][0] + cy) / 2 if i else float("-inf")
        lower = (cy + names[i + 1][0]) / 2 if i + 1 < len(names) else float("inf")
        row = Row(name=text, y=cy, cut=cut_end, unsure=unsure, guide=guides[i], confs=confs)
        mine = [n for n in nums if upper <= n[1] < lower]
        mid = statistics.median(n[1] for n in mine) if mine else cy
        for col in range(3):
            same = [n for n in mine if n[0] == col]
            if same:
                row.nums[col] = min(same, key=lambda n: abs(n[1] - mid))[2]
        rows.append(row)
    return rows


_PRESCRIPTION = re.compile(
    r"질병\s*분류\s*기호|의료\s*기관\s*명칭|요양\s*기관\s*기호"
)  # 처방전 서식 고유의 말 (약국 영수증도 "처방전 교부번호"는 적으므로 교부번호는 뺐다)
_INT = re.compile(r"\d{1,2}")


def _column_groups(fields: list[dict[str, Any]]) -> tuple[list[list[tuple[float, float]]], float]:
    """한두 자리 정수 낱말들을 가로 위치로 묶은 칸 후보들 (각 칸: [(가운데 x, 가운데 y)], 둘 이상일 때만)과 숫자 글자 높이"""
    ints = []
    for f in fields:
        if _INT.fullmatch(f["inferText"].strip()):
            b = _box(f)
            ints.append(((b[0] + b[2]) / 2, (b[1] + b[3]) / 2, max(b[3] - b[1], 1.0)))
    if not ints:
        return [], 1.0
    h = statistics.median(i[2] for i in ints)
    ints.sort()
    groups: list[list[tuple[float, float]]] = [[ints[0][:2]]]
    for x, y, _h in ints[1:]:
        if x - groups[-1][-1][0] > h:
            groups.append([(x, y)])
        else:
            groups[-1].append((x, y))
    return [g for g in groups if len(g) >= 2], h


def _valid_row_ys(cols: list[list[tuple[float, float]]], cx: list[float], h: float, names: list[Box]) -> list[float]:
    """세 칸의 숫자를 세로로 줄지은 것 중, 칸 둘 이상에 숫자가 있고 같은 높이에 한글 이름이 있는 줄들의 높이 (이름이 첫 칸 왼쪽에 있는지는 표를 읽을 때 본다)"""
    toks = sorted((y, k) for k, g in enumerate(cols) for _x, y in g)
    rows: list[list[tuple[float, int]]] = [[toks[0]]]
    for t in toks[1:]:
        if t[0] - statistics.mean(r[0] for r in rows[-1]) > 0.5 * h:
            rows.append([t])
        else:
            rows[-1].append(t)
    out = []
    for r in rows:
        y = statistics.mean(t[0] for t in r)
        named = any(abs((b[1] + b[3]) / 2 - y) <= 0.8 * h for b in names)
        if len({t[1] for t in r}) >= 2 and named:
            out.append(y)
    return out


def _regular_run(ys: list[float]) -> tuple[list[float], float]:
    """간격이 고른(중앙 간격의 ±40%) 가장 긴 연속 줄과 그 간격. 표 위 · 아래의 우연한 숫자는 간격이 달라 빠진다"""
    if len(ys) < 2:
        return [], 0.0
    pitch = statistics.median(b - a for a, b in zip(ys, ys[1:], strict=False))
    run: list[float] = [ys[0]]
    best: list[float] = []
    for y in ys[1:]:
        if abs((y - run[-1]) - pitch) <= 0.4 * pitch:
            run.append(y)
        else:
            best = max(best, run, key=len)
            run = [y]
    return max(best, run, key=len), pitch


def _headerless_columns(fields: list[dict[str, Any]]) -> tuple[list[float], float, float, float] | None:
    """머리글 없이 "약 이름 + 숫자 3개"만 줄지어 있는 목록(실제 p4_2016: 영수증 아래쪽 표)의 숫자 칸을 찾는다.
    (세 칸의 가운데 x, 숫자 글자 높이, 표 위쪽 y, 표 아래쪽 y) 또는 None.
    이웃한 세 묶음을 칸 후보로 보고, 줄마다 칸 둘 이상에 숫자와 왼쪽 한글 이름이 있는 줄이
    간격이 고르게 두 줄 이상 이어질 때만 표로 본다. 표 밖의 같은 위치 숫자(영수증 위쪽의 "투약일수 2" 등)는 이 범위에 들지 않는다"""
    groups, h = _column_groups(fields)
    names = [_box(f) for f in fields if _HANGUL.search(f["inferText"]) and len(_core(f["inferText"])) >= 3]
    best: tuple[int, list[float], float, float, float] | None = None
    for trio in zip(groups, groups[1:], groups[2:], strict=False):
        cx = [statistics.mean(x for x, _ in g) for g in trio]
        if not all(1.2 * h <= cx[i + 1] - cx[i] <= 15 * h for i in range(2)):
            continue
        run, pitch = _regular_run(_valid_row_ys(list(trio), cx, h, names))
        if len(run) >= 2 and (best is None or len(run) > best[0]):
            best = (len(run), cx, h, run[0] - pitch / 2, run[-1] + pitch / 2)
    return None if best is None else best[1:]


def _layout(
    fields: list[dict[str, Any]], head: tuple[int, int, int] | None
) -> tuple[list[float], float, float, float, bool] | None:
    """(세 칸의 가운데 x, 기준 글자 높이, 표 위쪽 y, 표 아래쪽 y, 머리글 없음 여부). 머리글이 있으면 그 위치, 없으면 목록에서 추정"""
    if head is None:
        if _PRESCRIPTION.search(" ".join(f["inferText"] for f in fields)):
            return None  # 머리글이 지워진 처방전을 약봉투 목록으로 읽지 않는다 (사진을 다시 찍게 함)
        cols = _headerless_columns(fields)
        return None if cols is None else (*cols, True)
    hb = [_box(fields[k]) for k in head]
    h = max(max(b[3] - b[1] for b in hb), 1.0)
    return [(b[0] + b[2]) / 2 for b in hb], h, max(b[3] for b in hb) - 0.2 * h, float("inf"), False


def parse_pouch(data: dict[str, Any]) -> Table | None:
    """약봉투 표 읽기. 머리글이 없거나 숫자가 있는 약 줄이 하나도 없으면 None.
    머리글은 없는데 "이름 + 숫자 3개" 줄이 줄지어 있으면 그 표를 읽되 `Table.headerless`로 표시한다"""
    fields = _merge_split_heads(data["images"][0]["fields"])
    head = _find_header(fields)
    layout = _layout(fields, head)
    if layout is None:
        return None
    cx, h, top, bottom, headerless = layout
    spacing = min(cx[1] - cx[0], cx[2] - cx[1])
    tol = max(0.7 * spacing, h)

    body: list[Item] = []
    for k, f in enumerate(fields):
        b = _box(f)
        if (head is None or k not in head) and top < (b[1] + b[3]) / 2 < bottom:
            body.append((f, b))

    nums: list[tuple[int, float, float]] = []  # (칸, 높이 위치, 값)
    in_cols: set[int] = set()  # 숫자 칸에서 읽은 낱말 (이름에 붙지 않게 이름 글자에서 뺀다)
    for f, b in body:
        if _NUM.fullmatch(f["inferText"].strip()):
            c = (b[0] + b[2]) / 2
            col = min(range(3), key=lambda i: abs(cx[i] - c))
            if abs(cx[col] - c) <= tol:
                nums.append((col, (b[1] + b[3]) / 2, float(f["inferText"].strip())))
                in_cols.add(id(f))

    if not nums:
        return None
    windows = _windows(_row_centers(nums, h), h)
    ends = windows[-1][1]  # 마지막 숫자 줄이 맡은 구간의 끝 — 그 아래(광고 · 안내 글자)는 표 밖이다
    zone = [
        (f, b)
        for f, b in body
        if id(f) not in in_cols and (b[0] + b[2]) / 2 <= cx[0] - 0.5 * spacing and (b[1] + b[3]) / 2 < ends
    ]  # 이름 칸: 숫자 칸 왼쪽, 표 안. 오른쪽의 영수증 띠는 들어오지 않는다
    names = _names(zone, h, windows)
    if not names:
        return None
    rows = _attach(names, nums, read_guidance(zone, [n[0] for n in names], h, ends))
    numbered = [i for i, r in enumerate(rows) if any(v is not None for v in r.nums)]
    if not numbered:
        return None
    # 숫자가 없는 줄이 표의 처음이나 끝에 있으면 표 바깥 글자(안내 문구 · 방문일 등)로 보고 버린다. 가운데는 약일 수 있어 남긴다
    rows = rows[numbered[0] : numbered[-1] + 1]
    # 줄 수 확인용 숫자 개수는 버린 줄의 숫자도 포함해 센다 (약 이름을 놓쳐 줄이 사라지면 `row_count_mismatch`로 사용자에게 알린다)
    n_anchor = max((sum(1 for n in nums if n[0] == col) for col in range(3)), default=0)
    return Table(rows=rows, n_anchor=n_anchor, disease_raw=None, headerless=headerless)


_SAME_LINE = 0.3  # 같은 줄로 묶는 세로 가운데 차이 (글자 높이 배). 위아래 두 줄 사이에 낀 값을 어느 쪽 줄에도 붙이지 않으려고 좁게 잡는다


def _line_texts(fields: list[dict[str, Any]]) -> list[str]:
    """같은 줄(세로 가운데 차이가 글자 높이의 `_SAME_LINE`배 안)의 낱말을 왼쪽부터 이어 붙인 줄 글.
    CLOVA 낱말 순서는 줄 순서가 아니고, "조 제 일"처럼 글자가 낱낱이 쪼개지기도 해서 줄로 묶어야 라벨이 이어진다.
    줄의 평균 높이와 견주어 묶는다 (바로 앞 낱말과만 견주면 위아래 줄이 사슬처럼 한 줄이 된다)"""
    items = sorted(((_box(f), f["inferText"]) for f in fields), key=lambda t: (t[0][1] + t[0][3]) / 2)
    lines: list[list[tuple[float, float, str]]] = []
    for (x0, y0, _x1, y1), text in items:
        cy, h = (y0 + y1) / 2, max(y1 - y0, 1.0)
        if lines and abs(sum(c for _x, c, _t in lines[-1]) / len(lines[-1]) - cy) <= _SAME_LINE * h:
            lines[-1].append((x0, cy, text))
        else:
            lines.append([(x0, cy, text)])
    return [" ".join(t for _x, _y, t in sorted(line)) for line in lines]


def dispensed_date(fields: list[dict[str, Any]], today: date | None = None) -> tuple[date | None, list[str]]:
    """약봉투의 조제일. "조제일" · "조제일자" 바로 뒤의 날짜들이 모두 같을 때만 쓰고, 다르면 비워 두고 확인하게 한다.
    (처방전의 교부일과 달리 약봉투에는 교부일이 없고, 조제일이 약을 받은 날이다 — ERD prescriptions.issued_date)"""
    today = today or date.today()
    found: set[date] = set()
    for text in _line_texts(fields):
        for m in _DATE.finditer(text):
            if not _LABEL.search(text[max(0, m.start() - 12) : m.start()]):
                continue
            try:
                d = date(int(m[1]), int(m[2]), int(m[3]))
            except ValueError:
                continue
            if 2000 <= d.year and d <= today:
                found.add(d)
    if len(found) == 1:
        return next(iter(found)), []
    return None, ["조제일 못 읽음" if not found else "조제일이 서로 다르게 적혀 있음"]
