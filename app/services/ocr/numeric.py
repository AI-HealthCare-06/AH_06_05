"""처방 숫자(1회량, 하루 횟수, 총 일수) 범위 검사. 벗어나면 "숫자를 확인해 주세요"로 사용자에게 되묻는다.

범위는 흔한 처방 기준으로 넉넉하게 잡은 값이며 약사 검토를 받은 기준이 아니다.
"""

from decimal import Decimal


def check(dose: float | Decimal | None, times: float | None, days: float | None) -> list[str]:
    """반환: 확인이 필요한 칸 이름 목록 (비면 통과)"""
    bad = []
    if dose is not None and not (0 < dose <= 10 and (float(dose) * 4) == int(float(dose) * 4)):  # 4분의 1정 단위
        bad.append("1회량")
    if times is not None and not (1 <= times <= 6 and times == int(times)):
        bad.append("하루 횟수")
    if days is not None and not (1 <= days <= 180 and days == int(days)):
        bad.append("총 일수")
    return bad
