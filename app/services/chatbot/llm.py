"""챗봇 OpenAI 호출 (#99). OCR 후보정(llm_fix.py)처럼 httpx만 쓰고 새 라이브러리는 넣지 않는다.

- 답은 JSON 스키마로 받는다 (strict). 형식이 어긋나면 LLMError
- 키는 config에서만 읽고 로그에 남기지 않는다. 질문 원문도 로그에 남기지 않는다
- 시험에서는 ChatClient 모양의 가짜를 넘겨 OpenAI를 부르지 않는다
"""

import json
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from app.core import config

OPENAI_URL = "https://api.openai.com/v1/chat/completions"
# 로컬 실험과 같음. 챗봇 작업 제한(arq 25초) 안에서 2층과 분류를 동시에 부르므로 한 번은 이 안에 끝나야 함
TIMEOUT_SEC = 15.0


class LLMError(Exception):
    """시간 초과, 연결 오류, 이상한 답. 부르는 쪽은 답을 만들지 않고 답변 오류(E6)로 보낸다"""


@dataclass
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    calls: int = 0

    def add(self, other: "Usage") -> None:
        self.prompt_tokens += other.prompt_tokens
        self.completion_tokens += other.completion_tokens
        self.calls += other.calls


class ChatClient(Protocol):
    async def complete_json(
        self, system: str, messages: list[dict[str, str]], schema: dict[str, Any], name: str, usage: Usage
    ) -> dict[str, Any]: ...


class OpenAIChat:
    """OpenAI 채팅 호출. temperature 0, JSON 스키마 답"""

    async def complete_json(
        self, system: str, messages: list[dict[str, str]], schema: dict[str, Any], name: str, usage: Usage
    ) -> dict[str, Any]:
        body = {
            "model": config.OPENAI_CHAT_MODEL,
            "temperature": 0,
            "messages": [{"role": "system", "content": system}, *messages],
            "response_format": {"type": "json_schema", "json_schema": {"name": name, "schema": schema, "strict": True}},
        }
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_SEC) as client:
                res = await client.post(
                    OPENAI_URL, json=body, headers={"Authorization": f"Bearer {config.OPENAI_API_KEY}"}
                )
                res.raise_for_status()
                data = res.json()
            used = data.get("usage") or {}
            usage.prompt_tokens += int(used.get("prompt_tokens", 0))
            usage.completion_tokens += int(used.get("completion_tokens", 0))
            usage.calls += 1
            result = json.loads(data["choices"][0]["message"]["content"])
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError) as e:
            raise LLMError(type(e).__name__) from e  # 예외 문장에 요청 내용이 섞이지 않게 종류 이름만
        if not isinstance(result, dict):
            raise LLMError("not_object")
        return result


def make_client() -> ChatClient:
    return OpenAIChat()
