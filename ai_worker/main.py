"""
AI Worker 진입점 (arq).

도커 컨테이너 안에서는 이 파일이 /app/main.py 가 되고 (Dockerfile에서
`COPY ./ai_worker ./` 로 내용물이 그대로 펼쳐져 들어갑니다. OCR 작업이 app 코드를 쓰므로 `COPY ./app ./app`도 함께), 로컬에서
돌려볼 때는 이 폴더(ai_worker/) 안에서 실행해야 같은 구조가 됩니다.

실행 방법
  로컬: cd ai_worker && uv run arq main.WorkerSettings
  컨테이너: arq main.WorkerSettings (Dockerfile CMD에 등록됨)
"""

import logging
import sys
from pathlib import Path
from typing import Any

from arq import cron, func
from arq.connections import RedisSettings
from tortoise import Tortoise

# 로컬에서 ai_worker/ 안에서 실행할 때도 app 패키지를 찾게 한다 (컨테이너에서는 app/이 main.py 옆에 있어 이미 보임)
_HERE = Path(__file__).resolve().parent
if not (_HERE / "app").is_dir() and (_HERE.parent / "app").is_dir() and str(_HERE.parent) not in sys.path:
    sys.path.append(str(_HERE.parent))

from core import config  # noqa: E402
from tasks import example_echo_task, ocr_job, purge_photos  # noqa: E402

from app.core import config as app_config  # noqa: E402
from app.core.db.databases import TORTOISE_ORM  # noqa: E402

logger = logging.getLogger(__name__)


async def startup(ctx: dict[str, Any]) -> None:
    """OCR 작업이 DB(Tortoise)를 쓰므로 시작할 때 연결하고, 약 이름 색인을 미리 만들어 첫 작업이 느려지지 않게 한다"""
    await Tortoise.init(config=TORTOISE_ORM)
    try:
        from app.services import prescriptions

        await prescriptions.get_matcher()
        await prescriptions.get_codes()
    except Exception:
        logger.exception("약 이름 색인을 미리 만들지 못함 (첫 OCR 작업에서 만듦)")


async def shutdown(ctx: dict[str, Any]) -> None:
    await Tortoise.close_connections()


class WorkerSettings:
    functions = [
        example_echo_task,
        # keep_result=0: 결과는 DB(ocr_jobs)에 있으니 Redis에 남기지 않는다
        func(
            ocr_job,
            name="ocr_job",
            timeout=app_config.OCR_WORKER_TIMEOUT_SEC,
            max_tries=app_config.OCR_WORKER_MAX_TRIES,
            keep_result=0,
        ),
    ]
    # 매시간 17분에 24시간 지난 사진 삭제 (S3 보관 규칙 1일은 마지막 안전장치)
    cron_jobs = [cron(purge_photos, minute={17}, run_at_startup=True, timeout=120)]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings(host=config.REDIS_HOST, port=config.REDIS_PORT)
    # 배포 서버 메모리가 1~2GB로 제한적이라, 동시 작업 수를 과하게 키우지 않습니다.
    # 10/2 메모리 측정 기준 유휴 ~31MB, 작업 5개 동시 처리해도 거의 변화 없음을 확인했습니다. (OCR 이전 뒤에는 약 이름 색인이 더해짐 — 배포 뒤 docker stats로 확인)
    max_jobs = 5
    # 업로드 API가 워커가 살아 있는지 이 키로 확인한다 (app/services/ocr/queue.py). 기본 1시간은 너무 길어 30초로
    health_check_interval = 30
    # 분석 상태(RG-01) 타임아웃 기준(60초)과 맞춤 — 안내문 생성 등 AI 호출이 30초를 넘을 수 있음. OCR은 위 func에서 따로 정함
    job_timeout = 60
