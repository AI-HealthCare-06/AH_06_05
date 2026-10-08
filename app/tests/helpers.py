"""테스트 공통 — API 명세서 A-1 모양의 회원가입 요청"""

from typing import Any

from httpx import AsyncClient

PASSWORD = "abcd1234"


def signup_payload(email: str, **overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "email": email,
        "password": PASSWORD,
        "nickname": "홍길동",
        "birthYear": 1958,
        "sex": "M",
        "consents": {"terms": True, "privacy": True, "sensitiveHealth": True},
    }
    payload.update(overrides)
    return payload


async def signup(client: AsyncClient, email: str, **overrides: Any) -> dict[str, Any]:
    response = await client.post("/api/v1/auth/signup", json=signup_payload(email, **overrides))
    assert response.status_code == 201, response.text
    return response.json()
