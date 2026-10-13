"""처방 약 표 읽기: "총 투약일수" 머리글 다음부터 "용법:" 전까지

약 이름 줄을 기준으로, 숫자는 글자 위치(머리글 "투약량", "투여횟수", "투약일수" 아래 칸)로 1회량 · 횟수 · 일수에 나눈다.
(순서로 나누면 숫자 하나를 못 읽을 때 뒤의 숫자가 한 칸씩 밀려서 엉뚱한 용량이 됨)
"""

import re
from dataclasses import dataclass, field
from typing import Any

from app.services.ocr.prepare import center

_NUM = re.compile(r"\d+(\.\d+)?")
_HEAD_WORDS = ((0, r"투[약여]량"), (1, r"투[약여]\s*횟수"), (2, r"투[약여]\s*일수"))
# 표가 끝났다는 표시: 약 줄 아래의 "조제시 참고사항", "주사제 처방내역", "사용기간", "이하 여백", 구분선 (실제 양식 5장 시험에서 추가)
_TABLE_END = re.compile(r"조제시|참고사항|주사제|사용기간|이하\s*여백|={3,}")
_SPLIT_HEAD = (re.compile(r"투[약여]"), re.compile(r"량|횟수|일수"))
# 질병분류기호 칸 뒤에서 값을 읽을 때 멈추는 말
_DZ_LABEL = r"질\s*병\s*분\s*류\s*기\s*호(?![를은는이가]\s*기재)"
_DZ_STOP = r"(?:처방|면허\s*종류|※|환자의\s*요구)"


@dataclass
class Row:
    name: str
    y: float
    nums: list[float | None] = field(default_factory=lambda: [None, None, None])  # [1회량, 하루 횟수, 총 일수]


@dataclass
class Table:
    rows: list[Row]
    n_anchor: int  # 숫자 칸 중 가장 많이 읽힌 칸의 숫자 수 (약 줄 수의 아래 한계)
    disease_raw: str | None  # 질병분류기호 원문


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
                    "inferText": a["inferText"] + b["inferText"],
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


def join_code_boxes(raw: str) -> str:
    """칸이 나뉜 질병분류기호("A 1 2 3 B 2 3 4")를 글자별로 붙임 → "A123 B234" """
    return re.sub(
        r"(?<![0-9A-Za-z])([A-Za-z])\s(\d)\s(\d)(?:\s(\d))?(?![0-9A-Za-z])",
        lambda m: "".join(g for g in m.groups() if g),
        raw,
    )


def parse_table(data: dict[str, Any]) -> Table | None:  # noqa: C901 — 시험 폴더에서 검증한 코드를 그대로 옮긴 것이라 나누지 않음
    """머리글을 못 읽으면 None (사진이 흐리거나 표가 잘림)"""
    fields = _merge_split_heads(data["images"][0]["fields"])
    tokens = [f["inferText"] for f in fields]
    text = " ".join(tokens)
    head = next((i for i, t in enumerate(tokens) if re.search(r"투[약여]\s*일수", t)), None)
    if head is None:
        return None
    start = head + 1
    end = next((i for i, t in enumerate(tokens) if t.startswith("용법")), len(tokens))
    # 약 줄 아래에 붙은 문구가 가짜 약 줄이 되지 않게, 표 끝 표시가 먼저 나오면 거기서 자른다
    end = min(end, next((i for i in range(start, len(tokens)) if _TABLE_END.match(tokens[i])), len(tokens)))

    col_x: dict[int, float] = {}
    for key, word in _HEAD_WORDS:
        hf = next((f for f in fields[:start] if re.search(word, f["inferText"])), None)
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
    gaps = sorted(b - a for a, b in zip(days_y, days_y[1:], strict=False) if b - a > 20)
    pitch = gaps[len(gaps) // 2] if gaps else None

    nums: list[dict[str, Any]] = []
    lines: list[dict[str, Any]] = []
    for f in fields[start:end]:
        if _NUM.fullmatch(f["inferText"]):
            nums.append(f)
            continue
        v = f["boundingPoly"]["vertices"]
        h = ((v[3]["x"] - v[0]["x"]) ** 2 + (v[3]["y"] - v[0]["y"]) ** 2) ** 0.5  # 왼쪽 변의 길이(기울어도 글자 높이)
        lines.append({"name": f["inferText"], "x": v[0]["x"], "y": level_y(f), "h": h})

    # 이름이 칸을 넘어 둘 이상의 줄이 되면 뒷줄을 앞 이름에 붙인다. 새 약이 시작되는 곳은 두 가지로 정한다.
    #  (1) 앞 줄과의 간격이 줄 간격(일수 칸 숫자 간격)의 절반 이상이거나 왼쪽 시작이 다를 때
    #  (2) 숫자 칸에 N개가 읽혔으면 약은 N줄이므로 줄 사이 간격이 큰 쪽 N-1곳도 새 약의 시작으로 본다
    split: set[int] = set()
    first_x = lines[0]["x"] if lines else 0
    for i in range(1, len(lines)):
        a, b = lines[i - 1], lines[i]
        limit = 0.5 * pitch if pitch else 1.4 * max(b["h"], 20)
        if 0 < b["y"] - a["y"] < limit and abs(b["x"] - first_x) < 40:
            continue
        split.add(i)
        first_x = b["x"]

    cnt = dict.fromkeys(col_x, 0)
    for f in fields[start:end]:
        if _NUM.fullmatch(f["inferText"]) and col_x:
            k = min(col_x, key=lambda k: abs(col_x[k] - center(f)[0]))
            if abs(col_x[k] - center(f)[0]) <= 120:
                cnt[k] += 1
    n_anchor = max(cnt.values(), default=0)
    if n_anchor >= 2 and len(lines) > 1:
        big = sorted(range(1, len(lines)), key=lambda i: lines[i]["y"] - lines[i - 1]["y"], reverse=True)[
            : n_anchor - 1
        ]
        split.update(i for i in big if lines[i]["y"] - lines[i - 1]["y"] > 0)

    rows: list[Row] = []
    for i, ln in enumerate(lines):
        if i in split or not rows:
            rows.append(Row(name=ln["name"], y=ln["y"]))
        else:
            rows[-1].name += ln["name"]
            rows[-1].y = (rows[-1].y + ln["y"]) / 2

    if len(col_x) == 3 and rows:
        for f in sorted(nums, key=lambda f: center(f)[0]):
            cx, cy = center(f)[0], level_y(f)
            row = min(rows, key=lambda r: abs(r.y - cy))
            col = min(col_x, key=lambda k: abs(col_x[k] - cx))
            if abs(row.y - cy) <= 40 and abs(col_x[col] - cx) <= 120 and row.nums[col] is None:
                row.nums[col] = float(f["inferText"])

    # 라벨이 "질병 분류 기호"로 쪼개져도 찾고, 아래 안내문("질병분류기호를 기재하지 …")은 건너뜀
    dz = re.search(_DZ_LABEL + r"\s*(.+?)\s*" + _DZ_STOP, text) or re.search(_DZ_LABEL + r"\s*(\S+)", text)
    return Table(rows=rows, n_anchor=n_anchor, disease_raw=join_code_boxes(dz[1]) if dz else None)
