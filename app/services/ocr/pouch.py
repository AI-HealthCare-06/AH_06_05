"""약봉투 표 읽기 — 처방전 표(table.py)와 머리글이 달라서 따로 읽는다 (10/15)

처방전은 "투약일수" 머리글을 기준으로 읽는다. 약봉투는 "투약량 · 횟수 · 일수"를 한 줄로 늘어놓은 표를 쓴다
(약봉투 샘플 3종 중 p1 · r2가 이 모양이고, p2는 같은 머리글이 "일수"를 "밀수"로 잘못 읽혀 지원하지 못한다).
처방전을 못 읽었을 때(`parse_table`이 None)만 이 함수를 부른다.

읽는 방법 (글자 순서가 아니라 위치로 읽는다 — CLOVA는 글자 목록 순서를 보장하지 않는다)
1. 같은 줄에서 왼쪽부터 "투약량 · 횟수 · 일수" 세 낱말이 모인 곳을 머리글로 본다.
2. 머리글 아래의 글자만 본다. 숫자는 세 칸 위치 안의 것만, 이름은 투약량 칸 왼쪽의 것만 읽는다.
   그래서 오른쪽의 영수증 띠(이름 · 주소 · 승인번호)는 읽지 않는다.
3. 약 이름 = 이름 칸의 **굵은(글자가 큰) 줄**. 카드형 표에는 이름 아래에 "[분류]" · 성분 줄과 복약 안내 문장이 있는데
   이들은 이름보다 글자가 작아서 이름이 되지 않는다 (글자 높이를 두 무리로 나눠 큰 쪽이 이름. 실제 p1: 이름 23~29, 나머지 15~21).
   이름은 이름 칸 왼쪽 끝에서 시작하고 "["로 시작하지 않는다. 한 줄짜리 표(r2)는 글자 높이가 거의 같아서 모든 줄이 이름이다.
4. 숫자는 머리글 세 낱말 아래 칸(가로 위치)으로 1회량 · 하루 횟수 · 총 일수에 나눈다.
   카드형 표는 숫자가 카드 가운데에 있어서, 이름 줄 사이의 가운데선으로 칸을 나눠 숫자를 이름에 붙인다.
5. 숫자가 하나도 읽히지 않은 줄이 표의 처음이나 끝에 있으면 표 바깥 글자(안내 문구 · 방문일 등)로 보고 버린다.
   표 가운데에서 숫자만 못 읽은 줄은 약일 수 있어서 남긴다 (사용자가 확인 · 입력).

이름 끝이 "···"로 잘린 줄은 `Row.cut`으로 표시하고, 파이프라인이 자동 확정하지 않고 사용자가 고르게 한다.

한계: 샘플 2종으로 만든 규칙이다. 이름이 두 줄로 꺾이면 줄마다 약 하나로 읽힐 수 있다 (이 경우 숫자 칸 수와 약 줄 수가
달라서 `row_count_mismatch`가 켜진다). 약봉투에 적힌 날짜는 `dispensed_date`가 읽는다.
"""

import re
import statistics
from datetime import date
from typing import Any

from app.services.ocr.table import _NUM, Row, Table, _merge_split_heads

_DOSE = re.compile(r"(?:투[약여])?량")
_TIMES = re.compile(r"(?:투[약여])?횟수")
_DAYS = re.compile(r"(?:투[약여])?일수")
_HANGUL = re.compile(r"[가-힣]")
_NAME_GAP = 1.2  # 이름 뒤에 이어 붙이는 조각과의 간격 한도 (머리글 글자 높이의 배수). 실측: 이름 뒤 함량은 0~6px, 이름 옆 안내 문장은 30px 이상
_SAME_SIZE = 0.7  # 이름 뒤에 이어 붙이는 조각(100mg 등)의 글자 높이가 이름 글자의 이 비율 이상일 때만 (실측 p1: 안내 문장 17~18 / 이름 24~29 = 0.75 이하, p3: 함량 "0.1%" 18 / 이름 20 = 0.9)
_NEAR_TALLEST = 0.9  # 구간 안에서 가장 큰 글자의 이 비율 이상인 줄 중 맨 위가 이름 (이름이 성분보다 약간만 커도, 숫자 없는 카드의 작은 줄이 섞여도 이름을 찾는다)
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


def _left_lines(zone: list[Item], h: float) -> list[tuple[float, str, bool, float]]:
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
    out: list[tuple[float, str, bool, float]] = []
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
                and -0.5 * h <= c[0] - last[2] <= _NAME_GAP * h  # 바로 오른쪽, 가까이 (상자가 살짝 겹쳐도 됨)
                and c[3] - c[1] >= _SAME_SIZE * height  # 이름보다 작은 글자(안내 문장)는 붙이지 않는다
                and min(b[3], c[3]) - max(b[1], c[1]) >= 0.5 * min(height, c[3] - c[1])  # 세로로 겹친다
            ]
            if not nxt:
                break
            kept.append(min(nxt, key=lambda t: t[1][0]))
        used.update(id(g) for g, _ in kept)
        text = _LEAD.sub("", "".join(_core(g["inferText"]) for g, _ in kept))
        cut_end = bool(_TAIL.search(text))
        text = _TAIL.sub("", text).strip()
        if text:
            out.append(((b[1] + b[3]) / 2, text, cut_end, statistics.median(c[3] - c[1] for _, c in kept)))
    return out


def _names(zone: list[Item], h: float, windows: list[tuple[float, float]]) -> list[tuple[float, str, bool]]:
    """약 이름 줄들: [(줄 높이 위치, 이름, 끝이 잘렸는지)].
    각 줄(카드)의 숫자가 맡은 구간 안에서, 가장 큰 글자에 가까운 줄 중 **맨 위 줄이 약 이름**이다. 카드형은 이름 아래에 성분 · 분류 · 안내가 오고, 한 줄형은 줄마다 구간이 하나다.
    (처음에는 글자 높이로 이름을 골랐는데, 실제 샘플 p3는 이름 19~22 · 성분 16~18로 차이가 작아 불안정했고 표 밖의 큰 광고 글자에도 흔들렸다)
    숫자를 하나도 못 읽은 약은 구간의 첫 줄이 아니어도, 이름 글자가 성분 글자보다 뚜렷이 클 때만 약으로 더한다."""
    lines = _left_lines(zone, h)
    if not lines or not windows:
        return []
    first_of: set[int] = set()
    for lo, hi in windows:
        inside = [i for i, ln in enumerate(lines) if lo <= ln[0] < hi]
        if inside:
            tallest = max(lines[i][3] for i in inside)
            near = [i for i in inside if lines[i][3] >= _NEAR_TALLEST * tallest]
            first_of.add(min(near, key=lambda i: lines[i][0]))
    others = [ln[3] for i, ln in enumerate(lines) if i not in first_of]
    cut = float("inf")
    if first_of and others:
        mean_name = statistics.mean(lines[i][3] for i in first_of)
        mean_other = statistics.mean(others)
        if mean_name > _SEPARATE * mean_other:
            cut = (mean_name + mean_other) / 2
    lo_all, hi_all = windows[0][0], windows[-1][1]
    keep = [ln for i, ln in enumerate(lines) if (i in first_of or (ln[3] >= cut and lo_all <= ln[0] < hi_all))]
    return [(cy, text, cut_end) for cy, text, cut_end, _ in keep]


def _attach(names: list[tuple[float, str, bool]], nums: list[tuple[int, float, float]]) -> list[Row]:
    """이름 줄 사이의 가운데선으로 나눈 칸 안의 숫자를 그 약에 붙인다 (카드형은 숫자가 카드 가운데에 있다)"""
    rows: list[Row] = []
    for i, (cy, text, cut_end) in enumerate(names):
        upper = (names[i - 1][0] + cy) / 2 if i else float("-inf")
        lower = (cy + names[i + 1][0]) / 2 if i + 1 < len(names) else float("inf")
        row = Row(name=text, y=cy, cut=cut_end)
        mine = [n for n in nums if upper <= n[1] < lower]
        mid = statistics.median(n[1] for n in mine) if mine else cy
        for col in range(3):
            same = [n for n in mine if n[0] == col]
            if same:
                row.nums[col] = min(same, key=lambda n: abs(n[1] - mid))[2]
        rows.append(row)
    return rows


def parse_pouch(data: dict[str, Any]) -> Table | None:
    """약봉투 표 읽기. 머리글이 없거나 숫자가 있는 약 줄이 하나도 없으면 None"""
    fields = _merge_split_heads(data["images"][0]["fields"])
    head = _find_header(fields)
    if head is None:
        return None
    hb = [_box(fields[k]) for k in head]
    h = max(max(b[3] - b[1] for b in hb), 1.0)
    cx = [(b[0] + b[2]) / 2 for b in hb]
    spacing = min(cx[1] - cx[0], cx[2] - cx[1])
    tol = max(0.7 * spacing, h)
    top = max(b[3] for b in hb) - 0.2 * h

    body: list[Item] = []
    for k, f in enumerate(fields):
        b = _box(f)
        if k not in head and (b[1] + b[3]) / 2 > top:
            body.append((f, b))

    nums: list[tuple[int, float, float]] = []  # (칸, 높이 위치, 값)
    for f, b in body:
        if _NUM.fullmatch(f["inferText"].strip()):
            c = (b[0] + b[2]) / 2
            col = min(range(3), key=lambda i: abs(cx[i] - c))
            if abs(cx[col] - c) <= tol:
                nums.append((col, (b[1] + b[3]) / 2, float(f["inferText"].strip())))

    if not nums:
        return None
    windows = _windows(_row_centers(nums, h), h)
    ends = windows[-1][1]  # 마지막 숫자 줄이 맡은 구간의 끝 — 그 아래(광고 · 안내 글자)는 표 밖이다
    names = _names(
        [(f, b) for f, b in body if (b[0] + b[2]) / 2 <= cx[0] - 0.5 * spacing and (b[1] + b[3]) / 2 < ends], h, windows
    )
    if not names:
        return None
    rows = _attach(names, nums)
    numbered = [i for i, r in enumerate(rows) if any(v is not None for v in r.nums)]
    if not numbered:
        return None
    # 숫자가 없는 줄이 표의 처음이나 끝에 있으면 표 바깥 글자(안내 문구 · 방문일 등)로 보고 버린다. 가운데는 약일 수 있어 남긴다
    rows = rows[numbered[0] : numbered[-1] + 1]
    # 줄 수 확인용 숫자 개수는 버린 줄의 숫자도 포함해 센다 (약 이름을 놓쳐 줄이 사라지면 `row_count_mismatch`로 사용자에게 알린다)
    n_anchor = max((sum(1 for n in nums if n[0] == col) for col in range(3)), default=0)
    return Table(rows=rows, n_anchor=n_anchor, disease_raw=None)


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
