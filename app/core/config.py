import os
import uuid
import zoneinfo
from dataclasses import field
from enum import StrEnum
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Env(StrEnum):
    LOCAL = "local"
    DEV = "dev"
    PROD = "prod"


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="allow")

    ENV: Env = Env.LOCAL
    SECRET_KEY: str = f"default-secret-key{uuid.uuid4().hex}"
    TIMEZONE: zoneinfo.ZoneInfo = field(default_factory=lambda: zoneinfo.ZoneInfo("Asia/Seoul"))
    TEMPLATE_DIR: str = os.path.join(Path(__file__).resolve().parent.parent, "templates")

    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str = "root"
    DB_PASSWORD: str = "pw1234"
    DB_NAME: str = "ai_health"
    DB_CONNECT_TIMEOUT: int = 5
    DB_CONNECTION_POOL_MAXSIZE: int = 10

    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    COOKIE_DOMAIN: str = "localhost"

    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 14 * 24 * 60
    JWT_LEEWAY: int = 5

    # CLOVA OCR (캠프 제공). 둘 다 비면 local · dev에서는 저장해 둔 가짜 처방전 결과로 대신 돌아감 (prod는 오류)
    CLOVA_OCR_INVOKE_URL: str = ""
    CLOVA_OCR_SECRET_KEY: str = ""

    # OCR 약 이름 후보정(LLM). 규칙이 못 찾은 약 이름 글자만 보내고, 고친 이름은 급여목록에서 다시 찾아 확인된 것만 "추천"으로 씀
    # (자동 확정 없음 — 사용자가 고름). 기본 꺼짐. 켜려면 OCR_LLM_FIX=true 와 OPENAI_API_KEY 가 모두 필요
    OCR_LLM_FIX: bool = False
    OPENAI_API_KEY: str = ""
    OPENAI_CHAT_MODEL: str = "gpt-4o-mini"
    OCR_LLM_TIMEOUT_SEC: float = 10.0
    OCR_LLM_MAX_NAMES: int = 8  # 처방전 한 장당 LLM에 보내는 약 이름 최대 개수 (비용 상한)

    # 안전성 점검(DUR) 자료 — 시험 폴더에서 만든 safety.sqlite 파일 경로 (읽기 전용). Postgres로 옮기기 전까지 이 파일을 읽음
    SAFETY_DB_PATH: str = ""
    # 복합제 구성 성분까지 보는 확장 (약사 검토 전이라 기본 꺼짐)
    SAFETY_COMBO_EXT: bool = False
