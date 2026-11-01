"""챗봇 답 만들기(H-3)를 arq 워커에 넣는다 (#118). 워커 쪽 작업 함수는 ai_worker/tasks/chatbot_tasks.py

Redis 연결과 워커 확인은 OCR 대기열(app/services/ocr/queue.py)과 같은 것을 쓴다.
꺼져 있거나 넣기에 실패하면 예외를 올리지 않고 False를 돌려준다. 부른 쪽이 서버 안 백그라운드 처리로 바꾼다.
"""

import asyncio
import logging

from app.core import config
from app.services.chats import STALE_SEC
from app.services.ocr import queue

logger = logging.getLogger(__name__)

CHAT_FUNCTION = "chat_answer"


async def enqueue_answer(message_id: int, emergency_dismissed: bool) -> bool:
    if not config.CHAT_WORKER:
        return False
    try:
        pool = await asyncio.wait_for(queue._get_pool(), timeout=5)
        if not await asyncio.wait_for(pool.exists(queue.WORKER_ALIVE_KEY), timeout=5):
            logger.warning("워커가 살아 있지 않아 챗봇 답을 서버 안에서 만듦 message=%s", message_id)
            return False
        # 같은 답 줄로 두 번 들어가지 않게 _job_id를 고정한다 (이미 있으면 None).
        # 워커가 OCR 작업으로 바빠 30초 안에 시작하지 못하면 버린다. 앱은 이미 포기했고, 다시 보내면 새 답 줄로 새 작업이 들어감
        queued = await asyncio.wait_for(
            pool.enqueue_job(
                CHAT_FUNCTION, message_id, emergency_dismissed, _job_id=f"chat-{message_id}", _expires=STALE_SEC
            ),
            timeout=5,
        )
    except Exception as e:
        logger.warning("챗봇 작업을 워커 대기열에 넣지 못함 message=%s (%s)", message_id, type(e).__name__)
        await queue.reset_pool()  # 끊긴 연결을 다음 요청에서 새로 만들게
        return False
    if queued is None:  # 같은 답 줄의 작업이 이미 대기열에 있음. 이미 맡겨진 것이므로 다시 만들지 않는다
        logger.info("챗봇 작업이 이미 대기열에 있음 message=%s", message_id)
    return True
