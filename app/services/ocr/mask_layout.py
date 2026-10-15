"""글자 위치(boundingPoly)로 이름 칸을 가린다 — 글자 순서로 찾는 규칙(mask.py)에 더하는 두 번째 안전장치 (10/15)

mask.py는 읽힌 순서의 글자열에서 "성명 바로 뒤" 같은 자리를 찾는다. 그래서 표를 세로로 읽어 이름이 라벨과 멀어지거나,
성씨 목록에 없는 이름이거나, 두 글자 이름이면 놓칠 수 있다. 여기서는 라벨(성명 · 이름 · 환자명 · 주치의 등)의 **위치**를 찾아
같은 줄의 오른쪽(칸 안)에 있는 한글 낱말을 순서와 상관없이 이름으로 보고 가린다. 라벨이 분명하면 성씨를 따지지 않는다.

- 라벨 아래 칸(라벨이 위, 값이 아래인 양식)은 보지 않는다. 실제 처방전에서 본 적이 없고, 시험에서 "성명" 아래의 "주차장" · "조제일자" 글자를 이름으로 오인했다.
- 양식 낱말(주민등록번호 · 의료기관 · 전화번호 등)과 mask.py의 낱말 목록에 있는 말은 가리지 않는다.
- 이름 칸이 비어 있거나 흐려서 글자가 없으면 가릴 것이 없다. 위치로도 못 찾는 이름은 mask.py 규칙이 마지막으로 다시 본다.
"""

import re
from typing import Any

from app.services.ocr.mask import _STOP, NAME, SURNAMES

# 라벨 낱말 (공백 · 콜론을 뺀 모양). "이름"은 일반 글에도 나오는 말이라 성씨 모양일 때만 가린다
_CLEAR_LABELS = frozenset(
    "성명 환자명 수진자명 수진자 피보험자명 피보험자 의사성명 의료인성명 주치의 담당의 담당의사 진료의 집도의 보호자 대리인 수령인".split()
)
_WEAK_LABELS = frozenset({"이름"})
_LABELS = _CLEAR_LABELS | _WEAK_LABELS
_LABEL_START = frozenset(word[:n] for word in _LABELS for n in range(1, len(word) + 1))

# 값이 아닌 양식 낱말: 두 글자짜리는 그대로 같을 때, 긴 라벨은 그 조각(세 글자 이상)일 때 이름 칸이 아니다.
# 조각만 보고 거르면 기호준 · 주민서 같은 실제 이름을 놓친다 (합성 시험에서 확인)
_FORM_WORDS_2 = frozenset(
    "명칭 주소 서명 날인 병원 의원 약국 처방 조제 교부 발행 생년 성별 연락 휴대 보험 번호 기관 의료 전화 팩스 면허 기호 분류 질병 등록 주민".split()
)
_FORM_WORDS_LONG = (
    "주민등록번호 주민번호 등록번호 의료기관 의료기관명칭 요양기관기호 전화번호 팩스번호 면허번호 질병분류기호 교부번호 처방전 조제기관 생년월일 이메일 휴대전화 연락처 의사면허 서명또는날인 약국명칭"
).split()
_BRACKET_SKIP = frozenset({"또는", "서명", "날인", "인"})

_HANGUL = re.compile(r"[가-힣]+")
_SURNAME_SHAPE = re.compile(rf"[{SURNAMES}][가-힣]{{1,3}}|(?:남궁|황보|제갈|선우|독고|사공|서문)[가-힣]{{2}}")
_MAX_NAME = 4
_VALUE_REACH = 8.0  # 라벨에서 값까지 떨어질 수 있는 거리 (라벨 글자 높이의 배수) — 칸 안에서 값이 오른쪽 끝에 있는 양식 (실측 최대 3.7배)
_NAME_GAP = 3.0  # 이름 글자 사이 · 괄호 뒤 간격 (높이의 배수)
_LABEL_GAP = 5.0  # 라벨 글자 사이 간격 ("성        명"처럼 양쪽 맞춤으로 벌어진 라벨, 실측 3.7배)


def _box(f: dict[str, Any]) -> tuple[float, float, float, float]:
    v = f["boundingPoly"]["vertices"]
    xs = [p["x"] for p in v]
    ys = [p["y"] for p in v]
    return min(xs), min(ys), max(xs), max(ys)


def _core(text: str) -> str:
    return re.sub(r"[\s:：]", "", text)


def _find_labels(fields: list[dict[str, Any]]) -> list[tuple[list[int], str]]:
    """같은 줄에서 오른쪽으로 이어지는 낱말(최대 4개)을 이어 붙여 라벨이 되는 구간: (낱말 번호들, 라벨). 읽힌 순서가 아니라 위치로 잇는다"""
    boxes = [_box(f) for f in fields]
    found: dict[int, tuple[list[int], str]] = {}
    for i, f in enumerate(fields):
        acc = _core(f["inferText"])
        if acc not in _LABEL_START:
            continue
        chain = [i]
        while True:
            if acc in _LABELS:
                found[i] = (list(chain), acc)  # 같은 시작이면 더 긴 라벨이 이긴다
            if len(chain) >= 4:
                break
            cur = boxes[chain[-1]]
            h = max(cur[3] - cur[1], 1.0)
            cy = (cur[1] + cur[3]) / 2
            nxt = [
                (boxes[k][0], k)
                for k in range(len(fields))
                if k not in chain
                and cur[2] - h * 0.3 <= boxes[k][0] <= cur[2] + h * _LABEL_GAP
                and abs((boxes[k][1] + boxes[k][3]) / 2 - cy) <= h * 0.7
                and _core(fields[k]["inferText"]) != ""
            ]
            if not nxt:
                break
            k = min(nxt)[1]
            acc += _core(fields[k]["inferText"])
            if acc not in _LABEL_START:
                break
            chain.append(k)
    return list(found.values())


def _is_value(token: str) -> bool:
    core = _core(token)
    if not _HANGUL.fullmatch(core) or core in _STOP:
        return False
    if core in _FORM_WORDS_2:
        return False
    return not (len(core) >= 3 and any(core in word or word in core for word in _FORM_WORDS_LONG))


def _row_after(fields: list[dict[str, Any]], members: list[int]) -> tuple[list[int], float, float]:
    """라벨과 같은 줄에서 라벨 오른쪽에 있는 낱말 번호(왼쪽부터), 라벨의 오른쪽 끝, 라벨 글자 높이"""
    boxes = [_box(fields[k]) for k in members]
    x1 = max(b[2] for b in boxes)
    y0 = min(b[1] for b in boxes)
    y1 = max(b[3] for b in boxes)
    h = max(y1 - y0, 1.0)
    cy = (y0 + y1) / 2
    row = []
    for k, f in enumerate(fields):
        b = _box(f)
        if k not in members and b[0] >= x1 - h * 0.3 and abs((b[1] + b[3]) / 2 - cy) <= h * 0.7:
            row.append((b[0], k))
    return [k for _, k in sorted(row)], x1, h


def _pick_right(fields: list[dict[str, Any]], lab: tuple[list[int], str]) -> list[int]:
    members, label = lab
    row, last, h = _row_after(fields, members)
    chosen: list[int] = []
    chars = 0
    reach = _VALUE_REACH
    for k in row:
        text = fields[k]["inferText"]
        core = _core(text)
        b = _box(fields[k])
        if b[0] - last > h * reach:
            break
        if not chosen and (core == "" or re.search(r"[()\[\]]", text) or core in _BRACKET_SKIP):
            last, reach = b[2], _NAME_GAP  # "(서명 또는 날인)" · 콜론은 건너뛴다
            continue
        if not _is_value(text):
            break
        if chars + len(core) > _MAX_NAME:
            if len(core) == 1 and chosen:
                return []  # 한 글자씩 이어지는 긴 줄(칸 이름 "투 약 일 수" 등)이다
            break
        chosen.append(k)
        chars += len(core)
        last, reach = b[2], _NAME_GAP
    value = "".join(_core(fields[k]["inferText"]) for k in chosen)
    split = any(
        len(_core(fields[k]["inferText"])) == 1 for k in chosen
    )  # 글자마다 쪼개진 값은 성씨로 시작해야 이름으로 본다
    if chars < 2 or ((split or label in _WEAK_LABELS) and not _SURNAME_SHAPE.fullmatch(value)):
        return []
    return chosen


def name_boxes(fields: list[dict[str, Any]]) -> set[int]:
    """이름 칸으로 보이는 글자 상자의 번호들"""
    hit: set[int] = set()
    try:
        for lab in _find_labels(fields):
            hit.update(_pick_right(fields, lab))
    except (KeyError, IndexError, TypeError, ValueError):
        return hit  # 위치가 이상한 사진은 위치로 가리지 않는다 (mask.py 규칙이 이어서 본다)
    return hit


def join_masked(fields: list[dict[str, Any]]) -> str:
    """글자들을 공백으로 이어 붙이되, 이름 칸의 연속된 상자는 [이름] 하나로 바꾼다"""
    hit = name_boxes(fields)
    out: list[str] = []
    prev_hit = False
    for k, f in enumerate(fields):
        if k in hit:
            if not prev_hit:
                out.append(NAME)
            prev_hit = True
            continue
        prev_hit = False
        out.append(f["inferText"])
    return " ".join(out)
