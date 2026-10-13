"""교부일 · 출생연도 읽기"""

import re
from datetime import date


def parse_meta(text: str, today: date | None = None) -> tuple[date | None, int | None, list[str]]:
    """반환: (교부일 또는 None, 출생연도 또는 None, 확인이 필요한 항목 목록)

    - 숫자 사이의 O, o, l, I는 0, 1로 본다 (2O26 → 2026)
    - "2026년 10월 01일", "2026.10.01", "2026-10-01", "2026/10/1" 모두 받는다. "1955년생", "생년 1955"도 받는다
    - 말이 안 되는 값(없는 날짜, 미래 교부일, 1900년 이전 또는 올해보다 뒤의 출생연도)은 None으로 두고 확인 항목에 적는다
    """
    today = today or date.today()
    t = re.sub(
        r"(?<=\d)[OoIl](?=[\d년월일.\-/])|(?<=[.\-/년월\s])[OoIl](?=\d)",
        lambda m: "0" if m.group(0) in "Oo" else "1",
        text,
    )
    flags: list[str] = []
    issued: date | None = None
    birth: int | None = None
    m = re.search(r"(\d{4})\s*[년.\-/]\s*(\d{1,2})\s*[월.\-/]\s*(\d{1,2})\s*일?", t)
    if m:
        try:
            issued = date(int(m[1]), int(m[2]), int(m[3]))
        except ValueError:
            flags.append("교부일이 달력에 없는 날짜")
        else:
            if issued > today:
                flags.append("교부일이 오늘보다 뒤")
                issued = None
            elif issued.year < 2000:
                flags.append("교부일이 너무 오래됨")
                issued = None
    else:
        flags.append("교부일 못 읽음")
    b = (
        re.search(r"(\d{4})\s*년\s*생", t)
        or re.search(r"생년[^\d]{0,8}(\d{4})", t)
        or re.search(r"(\d{4})\s*[가-힣]\s*생(?![가-힣])", t)
    )
    if b:
        y = int(b[1])
        if 1900 <= y <= today.year:
            birth = y
        else:
            flags.append("출생연도 범위 밖")
    else:
        flags.append("출생연도 못 읽음")
    return issued, birth, flags
