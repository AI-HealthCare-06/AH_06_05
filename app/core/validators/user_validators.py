import re
from datetime import datetime

from app.core import config

MIN_BIRTH_YEAR = 1900


def validate_password(password: str) -> str:
    """API A-1: 영문 + 숫자를 포함해 8자 이상"""
    if len(password) < 8 or not re.search(r"[A-Za-z]", password) or not re.search(r"[0-9]", password):
        raise ValueError("비밀번호는 영문과 숫자를 섞어 8자 이상으로 만들어 주세요.")
    return password


def validate_birth_year(birth_year: int) -> int:
    """API A-1: 1900 ~ 올해"""
    this_year = datetime.now(tz=config.TIMEZONE).year
    if not MIN_BIRTH_YEAR <= birth_year <= this_year:
        raise ValueError("태어난 해를 다시 확인해 주세요.")
    return birth_year
