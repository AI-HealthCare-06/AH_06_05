"""근거 검색이 쓰는 OpenAI 호출 (httpx만 사용, 새 라이브러리 없음). 시험에서는 같은 모양의 가짜로 바꿔 쓴다.

채팅은 시험 코드(rewrite_openai.call)와 같은 설정이다: 모델 gpt-4o-mini, temperature 0, 429/5xx는 최대 5번 다시 시도.
키는 로그에 남기지 않는다.
"""

import asyncio
from typing import Protocol

import httpx

from app.core import config

CHAT_MODEL = "gpt-4o-mini"  # v7 고정 설정. 서비스 모델 설정(OPENAI_CHAT_MODEL)이 바뀌어도 시험한 모델로 둔다
RETRY_STATUS = (429, 500, 502, 503)
MAX_ATTEMPTS = 5


class LLMError(RuntimeError):
    pass


class LLM(Protocol):
    async def complete(self, prompt: str) -> str: ...

    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class OpenAIClient:
    async def _post(self, path: str, body: dict) -> dict:
        if not config.OPENAI_API_KEY:
            raise LLMError("OPENAI_API_KEY가 없습니다")
        headers = {"Authorization": f"Bearer {config.OPENAI_API_KEY}"}
        async with httpx.AsyncClient(timeout=config.RAG_LLM_TIMEOUT_SEC) as client:
            for attempt in range(MAX_ATTEMPTS):
                try:
                    res = await client.post(f"https://api.openai.com/v1/{path}", json=body, headers=headers)
                except httpx.HTTPError as e:
                    if attempt == MAX_ATTEMPTS - 1:
                        raise LLMError(f"OpenAI 연결 실패: {type(e).__name__}") from e
                else:
                    if res.status_code == httpx.codes.OK:
                        return res.json()
                    if res.status_code not in RETRY_STATUS or attempt == MAX_ATTEMPTS - 1:
                        raise LLMError(f"OpenAI 오류 {res.status_code}")
                await asyncio.sleep(1.5 * (attempt + 1))
        raise LLMError("OpenAI 호출 실패")

    async def complete(self, prompt: str) -> str:
        data = await self._post(
            "chat/completions",
            {"model": CHAT_MODEL, "temperature": 0, "messages": [{"role": "user", "content": prompt}]},
        )
        return str(data["choices"][0]["message"]["content"]).strip()

    async def embed(self, texts: list[str]) -> list[list[float]]:
        data = await self._post("embeddings", {"model": config.OPENAI_EMBEDDING_MODEL, "input": texts})
        return [x["embedding"] for x in sorted(data["data"], key=lambda x: x["index"])]
