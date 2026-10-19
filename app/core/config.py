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

    # OCR 호출 전 흐린 사진 거르기: 글자가 가장 많은 칸 3개의 선명도가 이보다 낮으면 다시 찍게 함 (0이면 끔)
    # 근거: 10/13 시험 사진에서 못 읽힌 흐린 사진 11, 흐려도 읽힌 사진 232, 정상 사진 940 이상 (docs/design/ocr_precheck.md)
    OCR_MIN_SHARPNESS: float = 100.0

    # 사용자 한 명이 하루(한국 시간 자정부터)에 올릴 수 있는 사진 수 (0이면 끔). 처방전이 아닌 사진을 OCR 호출 전에 가려내는 것이
    # 어려워서(docs/design/ocr_precheck.md 시도 결과) CLOVA 호출 비용을 막는 안전장치로 둠
    OCR_DAILY_FILE_LIMIT: int = 30

    # OCR 약 이름 "비슷한 이름 추천" 기준 (자모 3글자 조각 유사도, 0이면 끔). 낮추면 더 많이 추천하지만 엉뚱한 약도 늘어남
    OCR_SIMILAR_MIN: float = 0.70

    # 읽힌 이름이 목록에 있어도 글자 하나 차이의 다른 성분 약(글리마릴정 ↔ 글리마릴엠정)이 있으면 자동 확정하지 않고 사용자가 고르게 함
    # (이름만으로는 오타와 다른 약을 구별할 수 없어서). 끄면 예전처럼 자동 확정 (docs/design/ocr_sibling.md)
    OCR_SIBLING_CONFIRM: bool = True

    # OCR 약 이름 후보정(LLM). 규칙이 못 찾은 약 이름 글자만 보내고, 고친 이름은 급여목록에서 다시 찾아 확인된 것만 "추천"으로 씀
    # (자동 확정 없음 — 사용자가 고름). 기본 꺼짐. 켜려면 OCR_LLM_FIX=true 와 OPENAI_API_KEY 가 모두 필요
    OCR_LLM_FIX: bool = False
    OPENAI_API_KEY: str = ""
    OPENAI_CHAT_MODEL: str = "gpt-4o-mini"
    OPENAI_EMBEDDING_MODEL: str = (
        "text-embedding-3-small"  # 근거 검색 임베딩 (1536차원, 바꾸면 evidence_chunks 벡터를 새로 만들어야 함)
    )
    RAG_LLM_TIMEOUT_SEC: float = 30.0  # 근거 검색 한 번의 OpenAI 호출 제한 시간 (재작성, 고르기, 판정, 임베딩 각각)
    OCR_LLM_TIMEOUT_SEC: float = 10.0
    OCR_LLM_MAX_NAMES: int = 8  # 처방전 한 장당 LLM에 보내는 약 이름 최대 개수 (비용 상한)

    # 안전성 점검(DUR) 자료 — 시험 폴더에서 만든 safety.sqlite 파일 경로 (읽기 전용). Postgres로 옮기기 전까지 이 파일을 읽음
    SAFETY_DB_PATH: str = ""
    # 복합제 구성 성분까지 보는 확장 (약사 검토 전이라 기본 꺼짐)
    SAFETY_COMBO_EXT: bool = False
