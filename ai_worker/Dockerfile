FROM python:3.13-slim

WORKDIR /app

# 1. uv 설치 (공식 이미지에서 복사해오는 가장 깔끔한 방법)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# 2. 의존성 패키지 관리 파일을 컨테이너 내부에 복사합니다.
COPY pyproject.toml uv.lock ./

# 3. pyproject.toml에 명시된 의존성 패키지 중에서 'ai'와 'app' 그룹을 설치합니다.
#    (OCR 작업이 app 코드를 그대로 쓰므로 app 그룹 — tortoise, boto3 등 — 이 필요합니다)
RUN uv sync --group ai --group app --no-dev --frozen

# 4. 로컬 소스 코드를 컨테이너 내부로 복사합니다. (WORKDIR이 이미 /app이라 ./ 로 바로 복사)
#    ai_worker 내용은 /app 바로 아래(main.py, core/, tasks/), app 코드는 /app/app 아래에 들어갑니다.
COPY ./ai_worker ./
COPY ./app ./app

# 5. arq 워커 실행 (WorkerSettings는 main.py에 정의)
CMD ["uv", "run", "--no-sync", "arq", "main.WorkerSettings"]
