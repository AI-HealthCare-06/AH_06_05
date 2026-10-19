import asyncio
from collections.abc import Generator
from typing import Any
from unittest.mock import Mock, patch

import pytest
import pytest_asyncio
from _pytest.fixtures import FixtureRequest
from tortoise import Tortoise, generate_config
from tortoise.contrib.test import finalizer, initializer

from app.core import config
from app.core.db.databases import TORTOISE_APP_MODELS

TEST_BASE_URL = "http://test"
TEST_DB_LABEL = "models"
TEST_DB_TZ = "Asia/Seoul"


def get_test_db_config() -> dict[str, Any]:
    tortoise_config = generate_config(
        db_url=f"postgres://{config.DB_USER}:{config.DB_PASSWORD}@{config.DB_HOST}:{config.DB_PORT}/test",
        app_modules={TEST_DB_LABEL: TORTOISE_APP_MODELS},
        connection_label=TEST_DB_LABEL,
        testing=True,
    )
    tortoise_config["timezone"] = TEST_DB_TZ

    return tortoise_config


_generate_schemas = Tortoise.generate_schemas


async def generate_schemas_with_extensions(safe: bool = True) -> None:
    """표를 만들기 전에 확장을 켠다 (evidence_chunks의 vector 칸과 pg_trgm 검색이 필요. CI와 도커 DB는 pgvector 이미지)"""
    await Tortoise.get_connection(TEST_DB_LABEL).execute_script(
        "CREATE EXTENSION IF NOT EXISTS vector; CREATE EXTENSION IF NOT EXISTS pg_trgm;"
    )
    await _generate_schemas(safe=safe)


@pytest.fixture(scope="session", autouse=True)
def initialize(request: FixtureRequest) -> Generator[None, None]:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    with (
        patch("tortoise.contrib.test.getDBConfig", Mock(return_value=get_test_db_config())),
        patch.object(Tortoise, "generate_schemas", generate_schemas_with_extensions),
    ):
        initializer(modules=TORTOISE_APP_MODELS)
    yield
    finalizer()
    loop.close()


@pytest_asyncio.fixture(autouse=True, scope="session")  # type: ignore[type-var]
def event_loop() -> None:
    pass
