"""표 해석 전 준비 단계

1) 사진 기울임 바로잡기: 글자마다 자기 글줄의 각도(왼쪽 위 → 오른쪽 위 꼭짓점 방향)를 재서 중앙값을 사진 전체 기울기로 보고,
   그만큼 좌표를 되돌려 돌린다. 기울기가 MAX_TILT도 넘으면 읽지 않고 다시 찍게 한다.
2) 숫자 칸 근처의 숫자 아닌 짧은 글자("3O", "l", "x" 등)는 숫자를 잘못 읽은 것이므로 지운다 (그 칸은 빈 칸으로 처리).
   (안 지우면 이런 글자가 약 이름 줄로 읽혀서 약 줄이 하나 더 생김)
"""

import copy
import math
import re
import statistics
from typing import Any

MAX_TILT = 20.0
_NUM = re.compile(r"\d+(\.\d+)?")


def center(f: dict[str, Any]) -> tuple[float, float]:
    v = f["boundingPoly"]["vertices"]
    return (v[0]["x"] + v[2]["x"]) / 2, (v[0]["y"] + v[2]["y"]) / 2


def tilt_degrees(fields: list[dict[str, Any]]) -> float:
    angs = []
    for f in fields:
        v = f["boundingPoly"]["vertices"]
        dx, dy = v[1]["x"] - v[0]["x"], v[1]["y"] - v[0]["y"]
        if dx > 20 and len(f["inferText"]) >= 2:
            angs.append(math.degrees(math.atan2(dy, dx)))
    return statistics.median(angs) if len(angs) >= 5 else 0.0


def prepare(data: dict[str, Any]) -> tuple[dict[str, Any], float, int, str]:
    """반환: (바로잡은 데이터, 기울기, 지운 글자 수, 상태) — 상태는 "ok" 또는 "too_tilted" """
    d = copy.deepcopy(data)
    fields = d["images"][0]["fields"]
    ang = tilt_degrees(fields)
    if abs(ang) > MAX_TILT:
        return d, ang, 0, "too_tilted"
    if abs(ang) > 0.5 and fields:
        xs = [v["x"] for f in fields for v in f["boundingPoly"]["vertices"]]
        ys = [v["y"] for f in fields for v in f["boundingPoly"]["vertices"]]
        cx, cy = sum(xs) / len(xs), sum(ys) / len(ys)
        a = math.radians(-ang)
        ca, sa = math.cos(a), math.sin(a)
        for f in fields:
            for v in f["boundingPoly"]["vertices"]:
                x, y = v["x"] - cx, v["y"] - cy
                v["x"], v["y"] = cx + x * ca - y * sa, cy + x * sa + y * ca
    tokens = [f["inferText"] for f in fields]
    head = next((i for i, t in enumerate(tokens) if re.search(r"투[약여]\s*일수", t)), None)
    removed = 0
    if head is not None:
        end = next((i for i, t in enumerate(tokens) if t.startswith("용법")), len(tokens))
        col_x = []
        for word in (r"투[약여]량", r"투[약여]\s*횟수", r"투[약여]\s*일수"):
            f = next((f for f in fields[: head + 1] if re.search(word, f["inferText"])), None)
            if f:
                col_x.append(center(f)[0])
        keep = []
        for i, f in enumerate(fields):
            t = f["inferText"]
            in_table = head < i < end and not _NUM.fullmatch(t)
            near_col = bool(col_x) and min(abs(center(f)[0] - x) for x in col_x) <= 60
            digit_like = re.search(r"[0-9OolIlSB]", t) is not None
            if in_table and near_col and (len(t) <= 2 or (len(t) <= 3 and digit_like)):
                removed += 1
                continue
            keep.append(f)
        d["images"][0]["fields"] = keep
    return d, ang, removed, "ok"
