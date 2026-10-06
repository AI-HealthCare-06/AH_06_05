from httpx import ASGITransport, AsyncClient
from starlette import status
from tortoise.contrib.test import TestCase

from app.main import app
from app.tests.helpers import signup


class TestUserMeApis(TestCase):
    async def test_get_user_me(self):
        """U-1: camelCase, 이메일은 로그인 아이디"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            tokens = await signup(client, "me@example.com")
            response = await client.get(
                "/api/v1/users/me", headers={"Authorization": f"Bearer {tokens['accessToken']}"}
            )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert set(body) == {"id", "email", "nickname", "birthYear", "sex", "createdAt"}
        assert body["email"] == "me@example.com"
        assert body["birthYear"] == 1958 and body["sex"] == "M" and body["nickname"] == "홍길동"

    async def test_update_user_me_only_sent_fields(self):
        """U-2: 보낸 칸만 바뀜"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            tokens = await signup(client, "update@example.com")
            headers = {"Authorization": f"Bearer {tokens['accessToken']}"}
            response = await client.patch(
                "/api/v1/users/me", json={"nickname": "길동", "birthYear": 1960}, headers=headers
            )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["nickname"] == "길동" and body["birthYear"] == 1960 and body["sex"] == "M"

    async def test_update_user_me_rejects_email(self):
        """U-2: email은 바꿀 수 없음 → VALIDATION_ERROR (field: email)"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            tokens = await signup(client, "noemail@example.com")
            headers = {"Authorization": f"Bearer {tokens['accessToken']}"}
            response = await client.patch("/api/v1/users/me", json={"email": "x@example.com"}, headers=headers)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        error = response.json()["error"]
        assert error["code"] == "VALIDATION_ERROR" and error["field"] == "email"

    async def test_get_user_me_unauthorized(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/users/me")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json() == {"error": {"code": "UNAUTHORIZED", "message": "로그인이 필요해요."}}
