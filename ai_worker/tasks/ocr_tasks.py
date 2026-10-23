"""OCR 작업 (O-1 업로드 뒤 사진 읽기). 실제 처리는 app/services/prescriptions.py의 run_queued_job 한 곳에 있고 여기서는 부르기만 한다.

흐름: 업로드 API가 사진을 저장소(S3)에 올리고 이 작업을 대기열에 넣는다 → 워커가 저장소에서 사진을 읽어 OCR을 돌린다.
CLOVA가 전부 실패하면 한 번만 더 시도한다 (횟수 · 간격은 app/core/config.py의 OCR_WORKER_*).
"""

from typing import Any

from arq import Retry

from app.core import config
from app.services import prescriptions


async def ocr_job(ctx: dict[str, Any], job_id: int, user_id: int) -> None:
    final = ctx.get("job_try", 1) >= config.OCR_WORKER_MAX_TRIES
    if await prescriptions.run_queued_job(job_id, user_id, final=final):
        raise Retry(defer=config.OCR_WORKER_RETRY_DELAY_SEC)
