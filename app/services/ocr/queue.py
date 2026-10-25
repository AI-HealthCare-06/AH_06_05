"""OCR 작업을 arq 워커(Redis 대기열)에 넣는다. 워커 쪽 작업 함수는 ai_worker/tasks/ocr_tasks.py

넣기에 실패해도 예외를 올리지 않고 False를 돌려준다 — 부른 쪽이 서버 안 백그라운드 처리로 바꾼다.
"""

import asyncio
import logging

from arq import ArqRedis, create_pool
from arq.connections import RedisSettings

from app.core import config

logger = logging.getLogger(__name__)

OCR_FUNCTION = "ocr_job"
# 워커가 health_check_interval(ai_worker/main.py, 30초)마다 갱신하는 키. 없으면 워커가 꺼져 있다고 보고 서버 안에서 처리한다
# (워커가 죽은 채로 작업을 넣으면 15분 뒤 실패로 닫힐 때까지 멈춰 있게 됨). 확인이 틀려도(잠깐 느려서) 서버 안 처리로 바뀔 뿐 오류는 아니다
WORKER_ALIVE_KEY = "arq:queue:health-check"
_pool: ArqRedis | None = None


def _settings() -> RedisSettings:
    # 연결이 안 될 때 업로드 응답이 오래 막히지 않게 짧게 포기한다
    return RedisSettings(
        host=config.REDIS_HOST, port=config.REDIS_PORT, conn_timeout=2, conn_retries=1, conn_retry_delay=0
    )


async def _get_pool() -> ArqRedis:
    global _pool
    if _pool is None:
        _pool = await create_pool(_settings())
    return _pool


async def reset_pool() -> None:
    """연결을 닫고 비운다 (서버 종료 · 테스트)"""
    global _pool
    pool, _pool = _pool, None
    if pool is not None:
        await pool.aclose()


async def enqueue_ocr(job_id: int, user_id: int) -> bool:
    try:
        pool = await asyncio.wait_for(_get_pool(), timeout=5)
        if not await asyncio.wait_for(pool.exists(WORKER_ALIVE_KEY), timeout=5):
            logger.warning("OCR 워커가 살아 있지 않아 서버 안에서 처리 job=%s", job_id)
            return False
        # 같은 작업 번호로 두 번 들어가지 않게 _job_id를 고정한다 (이미 있으면 None)
        queued = await asyncio.wait_for(
            pool.enqueue_job(OCR_FUNCTION, job_id, user_id, _job_id=f"ocr-{job_id}"), timeout=5
        )
    except Exception as e:
        logger.warning("OCR 작업을 워커 대기열에 넣지 못함 job=%s (%s)", job_id, type(e).__name__)
        await reset_pool()  # 끊긴 연결을 다음 요청에서 새로 만들게
        return False
    if queued is None:  # 같은 번호의 작업이 이미 대기열에 있음 — 이미 맡겨진 것이므로 다시 처리하지 않는다
        logger.info("OCR 작업이 이미 대기열에 있음 job=%s", job_id)
    return True
