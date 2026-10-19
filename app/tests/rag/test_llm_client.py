"""OpenAI 호출 도구 시험: 키 없음, 다시 시도, 실패 처리 (실제 호출 없음)"""

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.core import config
from app.services.rag import llm as llm_module
from app.services.rag.llm import MAX_ATTEMPTS, LLMError, OpenAIClient

_RealClient = httpx.AsyncClient


def run[T](coro: Awaitable[T]) -> T:
    """시험마다 자기 이벤트 루프를 만들어 쓴다 (전역 루프를 건드리면 DB 시험의 루프가 깨진다)"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)  # type: ignore[arg-type]
    finally:
        loop.close()


def with_transport(handler: Callable[[httpx.Request], httpx.Response]) -> Any:
    def factory(**kwargs: Any) -> httpx.AsyncClient:
        return _RealClient(transport=httpx.MockTransport(handler), **kwargs)

    return patch.object(llm_module.httpx, "AsyncClient", factory)


def chat(text: str) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": f" {text} "}}]})


def test_missing_key_raises() -> None:
    with patch.object(config, "OPENAI_API_KEY", ""), pytest.raises(LLMError):
        run(OpenAIClient().complete("안녕"))


def test_retries_rate_limit_then_succeeds() -> None:
    seen: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append({"auth": request.headers["authorization"], "body": request.content})
        return httpx.Response(429) if len(seen) < 3 else chat("답")

    with (
        patch.object(config, "OPENAI_API_KEY", "sk-test"),
        patch.object(llm_module.asyncio, "sleep", AsyncMock()),
        with_transport(handler),
    ):
        assert run(OpenAIClient().complete("질문")) == "답"
    assert len(seen) == 3 and seen[0]["auth"] == "Bearer sk-test"
    body = json.loads(seen[0]["body"])
    assert body["temperature"] == 0 and body["model"] == "gpt-4o-mini"


def test_gives_up_after_max_attempts() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(503)

    with (
        patch.object(config, "OPENAI_API_KEY", "sk-test"),
        patch.object(llm_module.asyncio, "sleep", AsyncMock()),
        with_transport(handler),
        pytest.raises(LLMError),
    ):
        run(OpenAIClient().complete("질문"))
    assert calls == MAX_ATTEMPTS


def test_attempts_and_timeout_can_be_set_per_client() -> None:
    calls = 0
    seen_timeout: list[Any] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(503)

    def factory(**kwargs: Any) -> httpx.AsyncClient:
        seen_timeout.append(kwargs.get("timeout"))
        return _RealClient(transport=httpx.MockTransport(handler), **kwargs)

    with (
        patch.object(config, "OPENAI_API_KEY", "sk-test"),
        patch.object(llm_module.asyncio, "sleep", AsyncMock()),
        patch.object(llm_module.httpx, "AsyncClient", factory),
        pytest.raises(LLMError),
    ):
        run(OpenAIClient(timeout_sec=3.5, max_attempts=2).complete("질문"))
    assert calls == 2 and seen_timeout == [3.5]
    assert OpenAIClient().max_attempts == MAX_ATTEMPTS and OpenAIClient().timeout_sec == config.RAG_LLM_TIMEOUT_SEC


def test_client_error_is_not_retried_and_hides_key() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(401, text="bad key sk-test")

    with patch.object(config, "OPENAI_API_KEY", "sk-test"), with_transport(handler):
        with pytest.raises(LLMError) as err:
            run(OpenAIClient().complete("질문"))
    assert calls == 1 and "sk-test" not in str(err.value)


def test_embed_sorts_by_index() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"index": 1, "embedding": [2.0]}, {"index": 0, "embedding": [1.0]}]})

    with patch.object(config, "OPENAI_API_KEY", "sk-test"), with_transport(handler):
        assert run(OpenAIClient().embed(["a", "b"])) == [[1.0], [2.0]]
