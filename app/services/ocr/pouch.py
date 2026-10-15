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
_UNIFORM = 1.3  # 이름 칸 글자 높이의 최대/최소가 이 값 이하면 한 줄형(모든 줄이 이름)
_BOLD = 0.85  # 이름 줄의 글자 높이 기준 (이름 줄 중 가장 큰 글자의 이 비율 이상)
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


def _height_cut(firsts: list[float]) -> float:
    """이름 칸 글자 높이를 두 무리(이름 / 성분 · 분류 · 안내)로 나눌 기준. 한 줄형(높이가 거의 같음)이면 0 = 모든 줄이 이름.
    실제 약봉투(p1)에서 이름 23~29, 나머지 15~21로 겹침이 좁아서, 상위 값이 아니라 두 무리의 가운데로 가른다"""
    small, big = min(firsts), max(firsts)
    if big <= _UNIFORM * small:
        return 0.0
    cut = (small + big) / 2
    for _ in range(20):
        low = [x for x in firsts if x < cut]
        up = [x for x in firsts if x >= cut]
        if not low or not up:
            break
        new_cut = (sum(low) / len(low) + sum(up) / len(up)) / 2
        if abs(new_cut - cut) < 0.01:
            break
        cut = new_cut
    return cut


def _names(zone: list[Item], h: float) -> tuple[list[tuple[float, str, bool]], float]:
    """이름 칸에서 약 이름 줄들: ([(줄 높이 위치, 이름, 끝이 잘렸는지)], 이름 글자 높이)"""
    cand = [(f, b) for f, b in zone if _HANGUL.search(f["inferText"])]
    if not cand:
        return [], 0.0
    edge = (
        min(b[0] for _, b in cand) + 2 * h
    )  # 이름은 이름 칸 왼쪽 끝에서 시작한다 (오른쪽의 안내 문장은 이름이 아니다)
    cut = _height_cut([b[3] - b[1] for _, b in cand if b[0] <= edge])
    # 이름 뒤에 붙은 "100mg" · "5/100" 같은 영문 · 숫자 조각도 같은 줄이면 이름에 이어 붙인다 (줄의 첫 글자는 한글이어야 한다)
    bold = sorted(((b[1] + b[3]) / 2, b[0], b[2], f) for f, b in zone if b[3] - b[1] >= cut)
    line_h = statistics.median(b[3] - b[1] for _, b in cand if b[3] - b[1] >= cut)
    lines: list[tuple[float, list[tuple[float, float, dict[str, Any]]]]] = []
    for cy, x0, x1, f in bold:
        if lines and cy - lines[-1][0] <= 0.6 * line_h:
            lines[-1][1].append((x0, x1, f))
        else:
            lines.append((cy, [(x0, x1, f)]))

    out: list[tuple[float, str, bool]] = []
    for cy, toks in lines:
        toks.sort(key=lambda t: t[0])
        first = _core(toks[0][2]["inferText"])
        if toks[0][0] > edge or not _HANGUL.search(first) or first.startswith("["):
            continue  # 왼쪽 끝에서 시작하지 않는 글자, "[당뇨병 치료제]" 같은 분류 줄
        kept = [toks[0]]
        for t in toks[1:]:
            if t[0] - kept[-1][1] > 3 * h:
                break  # 이름 줄 오른쪽에 떨어져 있는 다른 글자(안내 문장)는 이름에 붙이지 않는다
            kept.append(t)
        text = "".join(_core(f["inferText"]) for _, _, f in kept)
        text = _LEAD.sub("", text)
        cut_end = bool(_TAIL.search(text))
        text = _TAIL.sub("", text).strip()
        if text:
            out.append((cy, text, cut_end))
    return out, line_h


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

    names, line_h = _names([(f, b) for f, b in body if (b[0] + b[2]) / 2 <= cx[0] - 0.5 * spacing], h)
    if not names or not nums:
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


def dispensed_date(fields: list[dict[str, Any]], today: date | None = None) -> tuple[date | None, list[str]]:
    """약봉투의 조제일. "조제일" · "조제일자" 바로 뒤의 날짜들이 모두 같을 때만 쓰고, 다르면 비워 두고 확인하게 한다.
    (처방전의 교부일과 달리 약봉투에는 교부일이 없고, 조제일이 약을 받은 날이다 — ERD prescriptions.issued_date)"""
    today = today or date.today()
    text = " ".join(f["inferText"] for f in fields)
    found: set[date] = set()
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
