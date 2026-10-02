"""
AI Worker 진입점 (arq).

도커 컨테이너 안에서는 이 파일이 /app/main.py 가 되고 (Dockerfile에서
`COPY ./ai_worker ./app` 로 내용물이 그대로 펼쳐져 들어갑니다), 로컬에서
돌려볼 때는 이 폴더(ai_worker/) 안에서 실행해야 같은 구조가 됩니다.

실행 방법
  로컬: cd ai_worker && uv run arq main.WorkerSettings
  컨테이너: arq main.WorkerSettings (Dockerfile CMD에 등록됨)
"""

from arq.connections import RedisSettings
from core import config
from tasks import example_echo_task


class WorkerSettings:
    functions = [example_echo_task]
    redis_settings = RedisSettings(host=config.REDIS_HOST, port=config.REDIS_PORT)
    # 배포 서버 메모리가 1~2GB로 제한적이라, 동시 작업 수를 과하게 키우지 않습니다.
    # 10/2 메모리 측정 기준 유휴 ~31MB, 작업 5개 동시 처리해도 거의 변화 없음을 확인했습니다.
    max_jobs = 5
    # 분석 상태(RG-01) 타임아웃 기준(60초)과 맞춤 — 안내문 생성 등 AI 호출이 30초를 넘을 수 있음
    job_timeout = 60
