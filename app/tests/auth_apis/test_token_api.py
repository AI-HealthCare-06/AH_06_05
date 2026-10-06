from datetime import timedelta

from httpx import ASGITransport, AsyncClient
from starlette import status
from tortoise.contrib.test import TestCase

from app.core.jwt.tokens import AccessToken, RefreshToken
from app.main import app
from app.models.users import User
from app.tests.helpers import signup

REFRESH_URL = "/api/v1/auth/token/refresh"


class TestTokenRefreshAPI(TestCase):
    async def test_refresh_with_body(self):
        """A-4: 앱은 본문으로 재발급권을 보냄 (쿠키 없이)"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            tokens = await signup(client, "body@example.com")
            client.cookies.clear()
            response = await client.post(REFRESH_URL, json={"refreshToken": tokens["refreshToken"]})
        assert response.status_code == status.HTTP_200_OK
        assert set(response.json()) == {"accessToken"}
        assert AccessToken(response.json()["accessToken"]).payload["type"] == "access"

    async def test_refresh_with_cookie(self):
        """본문이 없으면 쿠키를 봄 (웹 · Swagger용)"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            tokens = await signup(client, "cookie@example.com")
            client.cookies.set("refresh_token", tokens["refreshToken"])
            response = await client.post(REFRESH_URL)
        assert response.status_code == status.HTTP_200_OK
        assert "accessToken" in response.json()

    async def test_refresh_missing(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(REFRESH_URL)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json()["error"]["code"] == "UNAUTHORIZED"

    async def test_refresh_rejects_access_token(self):
        """출입증을 재발급권 자리에 넣으면 거부 (토큰 종류 확인)"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            tokens = await signup(client, "swap1@example.com")
            client.cookies.clear()
            response = await client.post(REFRESH_URL, json={"refreshToken": tokens["accessToken"]})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json()["error"]["code"] == "UNAUTHORIZED"

    async def test_access_rejects_refresh_token(self):
        """재발급권을 출입증 자리(Authorization)에 넣으면 거부"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            tokens = await signup(client, "swap2@example.com")
            response = await client.get(
                "/api/v1/users/me", headers={"Authorization": f"Bearer {tokens['refreshToken']}"}
            )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json()["error"]["code"] == "UNAUTHORIZED"

    async def test_old_get_refresh_removed(self):
        """GET은 본문을 실을 수 없어서 POST로 바꿈"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(REFRESH_URL)
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    async def test_expired_tokens(self):
        """끝난 출입증 → 401 TOKEN_EXPIRED (앱은 A-4로 다시 받음), 끝난 재발급권 → 401 TOKEN_EXPIRED (다시 로그인)"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await signup(client, "expired@example.com")
            user = await User.get(login_id="expired@example.com")
            access = AccessToken.for_user(user)
            access.set_exp(lifetime=timedelta(minutes=-1))
            refresh = RefreshToken.for_user(user)
            refresh.set_exp(lifetime=timedelta(minutes=-1))
            client.cookies.clear()

            me = await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {access}"})
            again = await client.post(REFRESH_URL, json={"refreshToken": str(refresh)})

        for response in (me, again):
            assert response.status_code == status.HTTP_401_UNAUTHORIZED
            assert response.json()["error"]["code"] == "TOKEN_EXPIRED"
