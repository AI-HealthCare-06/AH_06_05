"""처방 약 표 읽기: "총 투약일수" 머리글 다음부터 "용법:" 전까지

약 이름 줄을 기준으로, 숫자는 글자 위치(머리글 "투약량", "투여횟수", "투약일수" 아래 칸)로 1회량 · 횟수 · 일수에 나눈다.
(순서로 나누면 숫자 하나를 못 읽을 때 뒤의 숫자가 한 칸씩 밀려서 엉뚱한 용량이 됨)
"""

import re
from dataclasses import dataclass, field
from typing import Any

from app.services.ocr.prepare import center, find_head, head_word

NEAR_MIDDLE = 0.3  # 숫자가 두 약 줄의 한가운데에서 줄 간격의 이 비율 안쪽에 있으면 어느 줄의 숫자인지 확실하지 않다
_NUM = re.compile(r"\d+(\.\d+)?")
_HEAD_WORDS = ((0, r"투[약여]량"), (1, r"투[약여]\s*횟수"), (2, r"투[약여]\s*일수"))
# 표가 끝났다는 표시: 약 줄 아래의 "조제시 참고사항", "주사제 처방내역", "사용기간", "이하 여백", 구분선 (실제 양식 5장 시험에서 추가)
_TABLE_END = re.compile(r"조제시|참고사항|주사제|사용기간|이하\s*여백|={3,}")
# 머리글이 "투약"+"량", "총투약"+"일수", "일투어"(여→어 오인)+"횟수"처럼 쪼개져 읽히는 경우 → 하나의 말로 합침
_SPLIT_HEAD = (re.compile(r"(?:총|일)?투[약여어]"), re.compile(r"량|횟수|일수"))
_SPLIT_CANON = {"량": "투약량", "횟수": "투여횟수", "일수": "투약일수"}
# 질병분류기호 칸 뒤에서 값을 읽을 때 멈추는 말
_DZ_LABEL = r"질\s*병\s*분\s*류\s*기\s*호(?![를은는이가]\s*기재)"
_DZ_LABEL_SHORT = r"분\s*류\s*기\s*호(?![를은는이가]\s*기재)"
_DZ_STOP = (
    r"(?:처\s*방|의료인|면허\s*종|※|환자의\s*요구|교\s*부)"  # 같은 줄의 "교부일: 2026년 …"까지 코드로 읽지 않게 (#237)
)


def _add_conf(row: "Row", c: Any) -> None:
    if isinstance(c, int | float):
        row.confs.append(float(c))


@dataclass
class Row:
    name: str
    y: float
    nums: list[float | None] = field(default_factory=lambda: [None, None, None])  # [1회량, 하루 횟수, 총 일수]
    unsure: bool = (
        False  # 약봉투: 이름 줄을 글자 크기로 골라야 했다 (구간 맨 위 줄이 이름 같지 않음). 사용자가 확인한다
    )
    guide: list[str] = field(
        default_factory=list
    )  # 약봉투: 약국이 약 아래에 인쇄한 복약 안내 표시 · 문장 (pouch_guide)
    cut: bool = False  # 이름 끝이 "···"로 잘려 있음 (약봉투). 뒷부분(함량 등)이 없어서 사용자가 확인한다
    confs: list[float] = field(default_factory=list)  # 이름을 이룬 글자 조각들의 CLOVA 인식 신뢰도
    timing: str | None = None  # 표에 "용법" 열이 있을 때 이 약 줄의 용법 칸 글자 (#237). 못 읽었으면 None
    nums_unsure: bool = False  # 숫자 줄이 이 약 줄과 이웃 약 줄의 한가운데쯤에 있어, 어느 약의 숫자인지 확실하지 않다. 사용자가 확인한다

    @property
    def conf(self) -> float | None:
        """이름 글자의 평균 인식 신뢰도 (값이 없으면 None)"""
        return sum(self.confs) / len(self.confs) if self.confs else None


@dataclass
class Table:
    rows: list[Row]
    n_anchor: int  # 숫자 칸 중 가장 많이 읽힌 칸의 숫자 수 (약 줄 수의 아래 한계)
    disease_raw: str | None  # 질병분류기호 원문
    headerless: bool = (
        False  # 약봉투에서 머리글 없이 "이름 + 숫자 3개" 목록을 읽음: 칸 순서(1회량 · 횟수 · 일수)는 추정이다
    )
    has_timing_col: bool = (
        False  # 머리글에 "용법" 칸이 있음 (#237). 이 경우 약마다 그 칸에서만 읽고, 못 읽은 줄은 비워 둔다
    )
    tail_text: str = ""  # 표 끝("용법:" 문구, 사용기간 등) 뒤의 글. 표 아래 "용법:" 한 줄은 여기서만 찾는다 (#237)
    above_timing: str | None = None  # 용법 칸이 없는 양식에서 표 위에 "용법: …" 한 줄이 있을 때 그 줄의 글


def _merge_split_heads(fields: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """머리글이 "투약"과 "량"처럼 쪼개져 읽히면 한 글자 묶음으로 합친다 (글자 위치는 두 칸을 감싸는 상자)"""
    out: list[dict[str, Any]] = []
    i = 0
    while i < len(fields):
        a = fields[i]
        b = fields[i + 1] if i + 1 < len(fields) else None
        if b and _SPLIT_HEAD[0].fullmatch(a["inferText"]) and _SPLIT_HEAD[1].fullmatch(b["inferText"]):
            pts = [(v["x"], v["y"]) for f in (a, b) for v in f["boundingPoly"]["vertices"]]
            x0, x1 = min(x for x, _ in pts), max(x for x, _ in pts)
            y0, y1 = min(y for _, y in pts), max(y for _, y in pts)
            out.append(
                {
                    **a,
                    "inferText": _SPLIT_CANON[b["inferText"]],
                    "inferConfidence": min(a.get("inferConfidence", 1.0), b.get("inferConfidence", 1.0)),
                    "boundingPoly": {
                        "vertices": [{"x": x0, "y": y0}, {"x": x1, "y": y0}, {"x": x1, "y": y1}, {"x": x0, "y": y1}]
                    },
                }
            )
            i += 2
        else:
            out.append(a)
            i += 1
    return out


def _box_height(f: dict[str, Any]) -> float:
    v = f["boundingPoly"]["vertices"]
    return float(((v[3]["x"] - v[0]["x"]) ** 2 + (v[3]["y"] - v[0]["y"]) ** 2) ** 0.5)


_LABEL_WORDS = {"질병", "분류", "기호", "질병분류", "분류기호", "질병분류기호"}
_STOP_WORDS = re.compile(r"^(?:처방?|의료인의|처방의료인의)$")


def _disease_by_position(fields: list[dict[str, Any]]) -> str | None:
    """라벨("질병 분류 기호") 오른쪽, "처방 의료인의" 왼쪽의 같은 높이 글자를 모아 코드로 읽는다.
    글자 목록 순서와 상관없고, 칸이 나뉜 숫자만 있는 코드("1 0 9" / "4 9 9" → "109 499")도 줄별로 붙인다"""
    label = [f for f in fields if f["inferText"] in _LABEL_WORDS]
    if len(label) < 2:
        return None
    ys = [center(f)[1] for f in label]
    right = max(max(v["x"] for v in f["boundingPoly"]["vertices"]) for f in label)
    y0, y1 = min(ys) - 14, max(ys) + 14
    stop = min(
        (
            center(f)[0]
            for f in fields
            if _STOP_WORDS.match(f["inferText"]) and y0 <= center(f)[1] <= y1 and center(f)[0] > right
        ),
        default=right + 400,
    )
    cand = [
        f
        for f in fields
        if f not in label
        and re.fullmatch(r"[A-Za-z0-9]{1,5}", f["inferText"])
        and y0 <= center(f)[1] <= y1
        and right < center(f)[0] < stop
    ]
    lines: list[list[dict[str, Any]]] = []
    for f in sorted(cand, key=lambda f: center(f)[1]):
        if lines and abs(center(f)[1] - center(lines[-1][-1])[1]) <= 10:
            lines[-1].append(f)
        else:
            lines.append([f])
    out = []
    for ln in lines:
        toks = [f["inferText"] for f in sorted(ln, key=lambda f: center(f)[0])]
        out.append("".join(toks) if all(len(t) == 1 for t in toks) else " ".join(toks))
    return " ".join(out) or None


def join_code_boxes(raw: str) -> str:
    """칸이 나뉜 질병분류기호("A 1 2 3 B 2 3 4")를 글자별로 붙임 → "A123 B234" """
    return re.sub(
        r"(?<![0-9A-Za-z])([A-Za-z])\s(\d)\s(\d)(?:\s(\d))?(?![0-9A-Za-z])",
        lambda m: "".join(g for g in m.groups() if g),
        raw,
    )


def _read_timing_column(
    fields: list[dict[str, Any]],
    rows: list[Row],
    head: int,
    col_x: dict[int, float],
    head_y: float,
    level_y: Any,
    end: int,
) -> bool:
    """머리글 줄에 "용법" 칸이 있으면(투약일수 오른쪽) 약 줄마다 그 칸의 글자를 읽어 Row.timing에 담는다.
    표 위의 "용법"을 처방전 전체 글에서 한 번만 읽어 모든 약에 붙이면, 칸 뒤의 다른 약 줄까지 읽힌다 (#237, 11/4 E2E).
    줄에 맞는 글자가 없으면 비워 둔다. 용법 칸이 없는 양식(표 아래 "용법: …" 한 줄)은 건드리지 않는다"""
    if 2 not in col_x or not rows:
        return False
    hh = _box_height(fields[head])
    yong = next(
        (
            f
            for f in fields
            if f["inferText"].startswith("용법") and abs(level_y(f) - head_y) <= hh and center(f)[0] > col_x[2] + 20
        ),
        None,
    )
    if yong is None:
        return False
    left = (col_x[2] + center(yong)[0]) / 2  # 일수 칸과 용법 칸 머리글의 가운데보다 오른쪽 글자가 용법 칸의 것이다
    floor = min((level_y(f) for f in fields[end:] if _TABLE_END.match(f["inferText"])), default=float("inf"))
    cells: dict[int, list[dict[str, Any]]] = {}
    for f in fields:
        if f is yong or _NUM.fullmatch(f["inferText"]) or center(f)[0] < left:
            continue
        y = level_y(f)
        if y <= head_y + 5 or y >= floor:
            continue
        i = min(range(len(rows)), key=lambda i: abs(rows[i].y - y))
        if abs(rows[i].y - y) <= 40:
            cells.setdefault(i, []).append(f)
    for i, group in cells.items():
        group.sort(key=lambda f: (round(level_y(f) / 10), center(f)[0]))
        text = " ".join(f["inferText"] for f in group).strip()
        rows[i].timing = text[:50] or None
    return True


def _timing_above(fields: list[dict[str, Any]], head_top: float, level_y: Any) -> str | None:
    """용법 칸이 없는 양식에서 "용법: …" 한 줄이 표 머리글 위에 있으면 그 줄의 글만 읽는다 (표 아래 줄은 Table.tail_text에서 읽음).
    콜론이 있는 "용법:"만 보고, 같은 줄(글자 높이 안)에서 그 오른쪽 글자만 모은다. 다른 줄까지 이어 읽지 않는다"""
    for i, f in enumerate(fields):
        t = f["inferText"]
        m = re.fullmatch(r"용법\s*[:：]\s*(.*)", t)
        split = (
            t == "용법" and i + 1 < len(fields) and fields[i + 1]["inferText"] in (":", "：")
        )  # "용법" ":"으로 나뉜 경우
        if not (m or split) or level_y(f) >= head_top:
            continue
        hh = _box_height(f)
        same = sorted(
            (g for g in fields if g is not f and abs(level_y(g) - level_y(f)) <= hh and center(g)[0] > center(f)[0]),
            key=lambda g: center(g)[0],
        )
        words = [m[1]] if m and m[1] else []
        for k, g in enumerate(same):
            w = g["inferText"]
            if re.match(r"사용기간|※", w):
                break
            if w in (":", "："):
                if k == 0:
                    continue  # "용법" 바로 뒤에 따로 읽힌 콜론
                break
            # 같은 줄의 다음 칸 이름("교부일:", "전화:", 또는 "교부일" ":"으로 나뉜 것)부터는 용법이 아니다
            if w.endswith((":", "：")) or (k + 1 < len(same) and same[k + 1]["inferText"] in (":", "：")):
                break
            words.append(w)
        text = " ".join(words).strip()
        if text:
            return text[:50]
    return None


def parse_table(data: dict[str, Any]) -> Table | None:  # noqa: C901 — 시험 폴더에서 검증한 코드를 그대로 옮긴 것이라 나누지 않음
    """머리글을 못 읽으면 None (사진이 흐리거나 표가 잘림)"""
    fields = _merge_split_heads(data["images"][0]["fields"])
    tokens = [f["inferText"] for f in fields]
    text = " ".join(tokens)
    head = find_head(fields)
    if head is None:
        return None
    start = head + 1
    # 표 끝을 알리는 "용법"은 머리글 줄보다 아래에 있는 것이다. 머리글의 "용법" 칸(투약일수 오른쪽)은 약 줄보다 앞 번호로 읽히기도 해서
    # (s1: "투약일수 : 용법 645400610 스타브론정 …") 번호만 보면 약 줄이 통째로 잘린다
    hy, hh = center(fields[head])[1], _box_height(fields[head])
    end = next(
        (i for i in range(start, len(tokens)) if tokens[i].startswith("용법") and center(fields[i])[1] > hy + hh),
        len(tokens),
    )
    # 약 줄 아래에 붙은 문구가 가짜 약 줄이 되지 않게, 표 끝 표시가 먼저 나오면 거기서 자른다
    end = min(
        end,
        next(
            (
                i
                for i in range(start, len(tokens))
                if _TABLE_END.match(tokens[i]) or "".join(tokens[i : i + 4]) == "이하여백"  # "이 하 여 백"
            ),
            len(tokens),
        ),
    )

    col_x: dict[int, float] = {}
    for key, word in _HEAD_WORDS:
        hf = head_word(fields, head, word)
        if hf:
            col_x[key] = center(hf)[0]

    # 사진이 기울었으면 같은 줄의 이름과 숫자의 높이가 달라지므로, 머리글 줄("명칭"과 "투약일수")로 기울기를 재서 바로잡는다
    slope = 0.0
    left = next((f for f in reversed(fields[:head]) if "명칭" in f["inferText"]), None)
    if left and 2 in col_x:
        lx, ly = center(left)
        rx, ry = center(fields[head])
        if abs(rx - lx) > 300:
            slope = (ry - ly) / (rx - lx)

    def level_y(f: dict[str, Any]) -> float:
        cx, cy = center(f)
        return cy - slope * cx

    # 줄 간격: 일수 칸 숫자들의 높이 차이의 중앙값 (이름이 두 줄인 줄도 있어서 평균 대신 중앙값).
    # 기울어진 사진에서는 옆 칸 숫자가 120 안에 들어올 수 있어서, 일수 칸이 가장 가까운 숫자만 센다
    days_y = sorted(
        level_y(f)
        for f in fields[start:end]
        if _NUM.fullmatch(f["inferText"])
        and 2 in col_x
        and abs(center(f)[0] - col_x[2]) <= 120
        and min(col_x, key=lambda k: abs(col_x[k] - center(f)[0])) == 2
    )
    # 같은 줄에서 읽힌 중복을 거르는 기준은 글자 높이의 절반(해상도가 낮은 사진은 줄 간격이 20px보다 작을 수 있음)
    heights = sorted(_box_height(f) for f in fields[start:end] if not _NUM.fullmatch(f["inferText"]))
    min_gap = max(0.5 * heights[len(heights) // 2], 5.0) if heights else 20.0
    gaps = sorted(b - a for a, b in zip(days_y, days_y[1:], strict=False) if b - a > min_gap)
    pitch = gaps[len(gaps) // 2] if gaps else None

    # CLOVA는 글자 목록 순서를 보장하지 않는다 (예: 총 투약일수 "90"이 머리글보다 앞 번호로 나옴). 머리글 아래에 있는 숫자는 번호가 달라도 같이 센다
    head_y = level_y(fields[head])
    out_of_slice = [
        f
        for i, f in enumerate(fields)
        if not start <= i < end and _NUM.fullmatch(f["inferText"]) and level_y(f) > head_y + 5
    ]

    # 약 이름은 숫자 칸(1회 투약량)보다 왼쪽에 있다. 오른쪽에서 읽힌 글자("용" "법" 머리글 등)는 약 줄이 아니다
    name_limit = min(col_x.values()) if col_x else float("inf")
    nums: list[dict[str, Any]] = []
    lines: list[dict[str, Any]] = []
    for f in fields[start:end]:
        if _NUM.fullmatch(f["inferText"]):
            nums.append(f)
            continue
        if center(f)[0] >= name_limit:
            continue
        v = f["boundingPoly"]["vertices"]
        h = ((v[3]["x"] - v[0]["x"]) ** 2 + (v[3]["y"] - v[0]["y"]) ** 2) ** 0.5  # 왼쪽 변의 길이(기울어도 글자 높이)
        lines.append({"name": f["inferText"], "x": v[0]["x"], "y": level_y(f), "h": h, "c": f.get("inferConfidence")})

    # 이름이 칸을 넘어 둘 이상의 줄이 되면 뒷줄을 앞 이름에 붙인다. 새 약이 시작되는 곳은 두 가지로 정한다.
    #  (1) 앞 줄과의 간격이 줄 간격(일수 칸 숫자 간격)의 절반 이상이거나 왼쪽 시작이 다를 때
    #  (2) 숫자 칸에 N개가 읽혔으면 약은 N줄이므로 줄 사이 간격이 큰 쪽 N-1곳도 새 약의 시작으로 본다
    split: set[int] = set()
    first_x = lines[0]["x"] if lines else 0
    for i in range(1, len(lines)):
        a, b = lines[i - 1], lines[i]
        if abs(b["y"] - a["y"]) < 0.5 * min(a["h"], b["h"]):
            continue  # 같은 줄에서 따로 읽힌 글자("스타브론정12.5MG" 옆의 "(제일)")는 같은 약 이름이다. 약은 줄이 달라야 나뉜다
        limit = 0.5 * pitch if pitch else 1.4 * max(b["h"], 20)
        if 0 < b["y"] - a["y"] < limit and abs(b["x"] - first_x) < 40:
            continue
        split.add(i)
        first_x = b["x"]

    nums.extend(out_of_slice)
    cnt = dict.fromkeys(col_x, 0)
    if col_x:
        # 줄마다 숫자를 모아 한 줄에 칸 수만큼 읽혔으면 왼쪽부터 순서대로 칸에 넣어 센다 (약 줄에 숫자를 쓰는 것과 같은 방식).
        # 머리글 가운데에서 먼 칸(넓은 칸의 왼쪽에 찍힌 숫자)을 가까운 옆 칸으로 세면 한 칸이 부풀어 줄 수 확인 안내가 거짓으로 뜬다 (#237 11/4 분석 37번)
        order = sorted(col_x, key=lambda k: col_x[k])
        by_line: list[list[dict[str, Any]]] = []
        cands = [f for f in [*fields[start:end], *out_of_slice] if _NUM.fullmatch(f["inferText"])]
        for f in sorted(cands, key=level_y):
            if by_line and abs(level_y(f) - level_y(by_line[-1][0])) <= min_gap:
                by_line[-1].append(f)
            else:
                by_line.append([f])
        for grp in by_line:
            grp.sort(key=lambda f: center(f)[0])
            if len(grp) == len(order):
                for k in order:
                    cnt[k] += 1
                continue
            for f in grp:
                k = min(col_x, key=lambda k: abs(col_x[k] - center(f)[0]))
                if abs(col_x[k] - center(f)[0]) <= 120:
                    cnt[k] += 1
    n_anchor = max(cnt.values(), default=0)
    if n_anchor >= 2 and len(lines) > 1:
        big = sorted(range(1, len(lines)), key=lambda i: lines[i]["y"] - lines[i - 1]["y"], reverse=True)[
            : n_anchor - 1
        ]
        split.update(i for i in big if lines[i]["y"] - lines[i - 1]["y"] > 0)

    # 급여 약품 코드(9자리 숫자)가 줄마다 왼쪽에 있는 양식은 코드가 약 하나의 시작이다. 이름이 두세 줄로 꺾여도 줄 간격을 추측하지 않고 코드로 나눈다
    anchors = sorted(
        level_y(f)
        for f in nums
        if re.fullmatch(r"\d{9}", f["inferText"]) and center(f)[0] < name_limit and level_y(f) > head_y
    )
    rows: list[Row] = []
    if len(anchors) >= 2:
        rows = [Row(name="", y=a) for a in anchors]
        for ln in lines:
            owner = max((i for i, a in enumerate(anchors) if ln["y"] >= a - 8), default=None)
            if owner is not None:
                rows[owner].name += ln["name"]
                _add_conf(rows[owner], ln["c"])
        rows = [r for r in rows if r.name]
    else:
        for i, ln in enumerate(lines):
            if i in split or not rows:
                rows.append(Row(name=ln["name"], y=ln["y"]))
            else:
                rows[-1].name += ln["name"]
                rows[-1].y = (rows[-1].y + ln["y"]) / 2
            _add_conf(rows[-1], ln["c"])

    if len(col_x) == 3 and rows:
        # 줄마다 숫자를 모은다. 한 줄에 정확히 3개가 읽혔으면 왼쪽부터 순서대로 1회량 · 횟수 · 일수로 본다
        # (숫자가 칸 중심에서 치우쳐 있으면 옆 칸에 더 가까워 보일 수 있어서). 개수가 다르면 가장 가까운 칸으로 정한다
        per_row: dict[int, list[dict[str, Any]]] = {}
        for f in nums:
            cx, cy = center(f)[0], level_y(f)
            by_dist = sorted(range(len(rows)), key=lambda i: abs(rows[i].y - cy))
            i = by_dist[0]
            if abs(rows[i].y - cy) <= 40 and any(abs(c - cx) <= 120 for c in col_x.values()):
                per_row.setdefault(i, []).append(f)
                if len(by_dist) > 1:
                    j = by_dist[1]
                    gap = abs(rows[j].y - rows[i].y)
                    # 숫자가 두 약 줄의 한가운데쯤에 있으면(가까운 쪽과 먼 쪽의 거리 차이가 줄 간격의 30% 미만) 흔들림 하나에 이웃 줄로 넘어갈 수 있다
                    if gap > 0 and (abs(rows[j].y - cy) - abs(rows[i].y - cy)) < NEAR_MIDDLE * gap:
                        rows[i].nums_unsure = rows[j].nums_unsure = True
        order = sorted(col_x, key=lambda k: col_x[k])
        for i, group in per_row.items():
            group.sort(key=lambda f: center(f)[0])
            if len(group) == len(order):
                for k, f in zip(order, group, strict=True):
                    rows[i].nums[k] = float(f["inferText"])
                continue
            for f in group:
                col = min(col_x, key=lambda k: abs(col_x[k] - center(f)[0]))
                if abs(col_x[col] - center(f)[0]) <= 120 and rows[i].nums[col] is None:
                    rows[i].nums[col] = float(f["inferText"])

    # 라벨이 "질병 분류 기호"로 쪼개져도 찾고, 아래 안내문("질병분류기호를 기재하지 …")은 건너뜀
    # 양식에 따라 "질병 분류 기호 A123"이거나 "분류 기호 B 2 3 4 질병 A 1 2 3"(줄마다 코드가 따로)이다. 뒤쪽 양식은 사이의 "질병"을 지운다
    dz = (
        re.search(_DZ_LABEL + r"\s*(.*?)\s*" + _DZ_STOP, text)
        or re.search(_DZ_LABEL_SHORT + r"\s*(.*?)\s*" + _DZ_STOP, text)
        or re.search(_DZ_LABEL + r"\s*(\S+)", text)
    )
    raw = re.sub(r"\s*질병\s*", " ", dz[1]).strip() if dz else None
    raw = raw or _disease_by_position(fields)
    has_timing_col = _read_timing_column(fields, rows, head, col_x, head_y, level_y, end)
    return Table(
        rows=rows,
        n_anchor=n_anchor,
        disease_raw=join_code_boxes(raw) if raw else None,
        has_timing_col=has_timing_col,
        tail_text=" ".join(tokens[end:]),
        above_timing=None if has_timing_col else _timing_above(fields, head_y - hh, level_y),
    )
