"""가입하지 않은 이메일의 로그인 실패 횟수와 잠김 (API 명세서 A-2 "같은 에러")

가입한 회원은 users.failed_login_count, locked_until에 셈. 가입하지 않은 이메일은 셀 줄이 없어서
Redis에 같은 규칙(5번 틀리면 10분 잠김)으로 셈. 그래야 남은 횟수와 잠김으로 가입 여부가 드러나지 않음.
이메일은 그대로 두지 않고 소문자로 바꾼 뒤 SHA-256으로 키를 만듦.
"""

import hashlib
from datetime import datetime, timedelta

from redis.asyncio import Redis

from app.core import config

COUNT_PREFIX = "login_fail:"
LOCK_PREFIX = "login_lock:"
COUNT_TTL_SECONDS = 24 * 60 * 60  # 아무 이메일이나 넣어 키가 끝없이 쌓이지 않게 하루 뒤 지움


def _key(email: str) -> str:
    return hashlib.sha256(email.strip().lower().encode()).hexdigest()


def _redis() -> Redis:
    # 요청마다 새로 연결함 (시험과 서버의 이벤트 루프가 달라도 문제없게). 실패한 로그인에서만 부름
    return Redis(host=config.REDIS_HOST, port=config.REDIS_PORT, decode_responses=True)


async def locked_until(email: str) -> datetime | None:
    async with _redis() as r:
        value = await r.get(LOCK_PREFIX + _key(email))
    return datetime.fromisoformat(str(value)) if value else None


async def record_failure(
    email: str, *, max_failures: int, lock_minutes: int, now: datetime
) -> tuple[int, datetime | None]:
    """틀린 횟수 +1. max_failures에 닿으면 횟수를 지우고 잠금. (이번이 몇 번째인지, 잠금 시각)"""
    key = _key(email)
    async with _redis() as r:
        failures = await r.incr(COUNT_PREFIX + key)
        await r.expire(COUNT_PREFIX + key, COUNT_TTL_SECONDS)
        if failures < max_failures:
            return failures, None
        lock_until = now + timedelta(minutes=lock_minutes)
        await r.delete(COUNT_PREFIX + key)
        await r.set(LOCK_PREFIX + key, lock_until.isoformat(), ex=lock_minutes * 60)
        return failures, lock_until


async def clear(email: str) -> None:
    key = _key(email)
    async with _redis() as r:
        await r.delete(COUNT_PREFIX + key, LOCK_PREFIX + key)
