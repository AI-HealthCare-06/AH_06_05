import time
from email.utils import parsedate_to_datetime

from httpx import ASGITransport, AsyncClient
from starlette import status
from tortoise.contrib.test import TestCase

from app.core.jwt.tokens import AccessToken, RefreshToken
from app.main import app
from app.models.users import User
from app.tests.helpers import PASSWORD, signup


class TestLoginAPI(TestCase):
    async def test_login_success(self):
        """A-2: 출입증 · 재발급권(본문) · 내 정보, 재발급권 쿠키도 같이"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await signup(client, "login@example.com")
            response = await client.post(
                "/api/v1/auth/login", json={"email": "login@example.com", "password": PASSWORD}
            )

        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert set(body) == {"accessToken", "refreshToken", "user"}
        assert body["user"]["nickname"] == "홍길동"
        assert AccessToken(body["accessToken"]).payload["type"] == "access"
        assert RefreshToken(body["refreshToken"]).payload["type"] == "refresh"
        assert any(h.startswith("refresh_token=") for h in response.headers.get_list("set-cookie"))

    async def test_login_unknown_email_and_wrong_password_same_error(self):
        """이메일이 없을 때와 비밀번호가 틀렸을 때 같은 코드 · 문구"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await signup(client, "same@example.com")
            unknown = await client.post("/api/v1/auth/login", json={"email": "none@example.com", "password": PASSWORD})
            wrong = await client.post("/api/v1/auth/login", json={"email": "same@example.com", "password": "wrong123"})

        for response in (unknown, wrong):
            assert response.status_code == status.HTTP_401_UNAUTHORIZED
            assert response.json()["error"]["code"] == "AUTH_INVALID_CREDENTIALS"
            assert response.json()["error"]["message"] == "이메일 또는 비밀번호가 맞지 않아요."
        assert wrong.json()["error"]["detail"] == {"remainingAttempts": 4}

    async def test_login_locked_after_five_failures(self):
        """CM-01-E1 남은 횟수 → 5번째에 CM-01-E2 잠금 (맞는 비밀번호도 10분 동안 거부)"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await signup(client, "lock@example.com")
            remaining = []
            for _ in range(4):
                r = await client.post("/api/v1/auth/login", json={"email": "lock@example.com", "password": "wrong123"})
                remaining.append(r.json()["error"]["detail"]["remainingAttempts"])
            fifth = await client.post("/api/v1/auth/login", json={"email": "lock@example.com", "password": "wrong123"})
            right = await client.post("/api/v1/auth/login", json={"email": "lock@example.com", "password": PASSWORD})

        assert remaining == [4, 3, 2, 1]
        for response in (fifth, right):
            assert response.status_code == status.HTTP_423_LOCKED
            error = response.json()["error"]
            assert error["code"] == "AUTH_LOCKED"
            assert error["detail"]["lockedUntil"].endswith("+09:00")

    async def test_login_unlocks_after_lock_time(self):
        """잠금 시각이 지나면 다시 로그인되고, 틀린 횟수는 0부터 다시 셈"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await signup(client, "unlock@example.com")
            for _ in range(5):
                await client.post("/api/v1/auth/login", json={"email": "unlock@example.com", "password": "wrong123"})
            user = await User.get(login_id="unlock@example.com")
            user.locked_until = user.locked_until.replace(year=2000)  # 잠금이 이미 지난 것처럼
            await user.save(update_fields=["locked_until"])

            wrong = await client.post(
                "/api/v1/auth/login", json={"email": "unlock@example.com", "password": "wrong123"}
            )
            right = await client.post("/api/v1/auth/login", json={"email": "unlock@example.com", "password": PASSWORD})

        assert wrong.json()["error"]["detail"] == {"remainingAttempts": 4}
        assert right.status_code == status.HTTP_200_OK
        user = await User.get(login_id="unlock@example.com")
        assert user.failed_login_count == 0 and user.locked_until is None

    async def test_login_token_lifetimes(self):
        """출입증 60분 · 재발급권 14일 · 쿠키 14일 (PR #45 버그 3개 다시 생기지 않게)"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await signup(client, "lifetime@example.com")
            response = await client.post(
                "/api/v1/auth/login", json={"email": "lifetime@example.com", "password": PASSWORD}
            )

        body = response.json()
        cookie = next(h for h in response.headers.get_list("set-cookie") if h.startswith("refresh_token="))
        expires = next(p.split("=", 1)[1] for p in cookie.split("; ") if p.lower().startswith("expires="))
        day = 24 * 60 * 60
        assert 55 * 60 < AccessToken(body["accessToken"]).payload["exp"] - time.time() < 65 * 60
        assert 13 * day < RefreshToken(body["refreshToken"]).payload["exp"] - time.time() < 15 * day
        assert 13 * day < parsedate_to_datetime(expires).timestamp() - time.time() < 15 * day
