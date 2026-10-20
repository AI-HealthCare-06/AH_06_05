import time
import uuid
from email.utils import parsedate_to_datetime
from unittest.mock import patch

from httpx import ASGITransport, AsyncClient
from redis.exceptions import ConnectionError as RedisConnectionError
from starlette import status
from tortoise.contrib.test import TestCase

from app.core.jwt.tokens import AccessToken, RefreshToken
from app.main import app
from app.models.users import User
from app.services import unknown_email_attempts
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
        assert set(body["user"]) == {"id", "birthYear", "sex"}  # 별명 없음(#96), 건강 정보는 U-1에서만
        assert AccessToken(body["accessToken"]).payload["type"] == "access"
        assert RefreshToken(body["refreshToken"]).payload["type"] == "refresh"
        assert any(h.startswith("refresh_token=") for h in response.headers.get_list("set-cookie"))

    async def test_login_unknown_email_and_wrong_password_same_error(self):
        """이메일이 없을 때와 비밀번호가 틀렸을 때 같은 코드 · 문구"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await signup(client, "same@example.com")
            none_email = f"none-{uuid.uuid4().hex[:8]}@example.com"  # Redis 횟수가 시험마다 쌓이지 않게
            unknown = await client.post("/api/v1/auth/login", json={"email": none_email, "password": PASSWORD})
            wrong = await client.post("/api/v1/auth/login", json={"email": "same@example.com", "password": "wrong123"})

        for response in (unknown, wrong):
            assert response.status_code == status.HTTP_401_UNAUTHORIZED
            assert response.json()["error"]["code"] == "AUTH_INVALID_CREDENTIALS"
            assert response.json()["error"]["message"] == "이메일 또는 비밀번호가 맞지 않아요."
            # 가입 여부가 드러나지 않게 detail 모양도 같음
            assert response.json()["error"]["detail"] == {"remainingAttempts": 4}

    async def test_login_unknown_email_counts_and_locks_like_real_account(self):
        """가입하지 않은 이메일도 남은 횟수가 4 → 1로 줄고 5번째에 잠김. 응답만으로 가입 여부를 알 수 없게 (A-2 같은 에러)"""
        unknown_email = f"nobody-{uuid.uuid4().hex[:8]}@example.com"
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await signup(client, "real-lock@example.com")
            results = {}
            for email in ("real-lock@example.com", unknown_email):
                responses = [
                    await client.post("/api/v1/auth/login", json={"email": email, "password": "wrong123"})
                    for _ in range(5)
                ]
                results[email] = responses

        for responses in results.values():
            assert [r.status_code for r in responses] == [401, 401, 401, 401, 423]
            assert [r.json()["error"].get("detail") for r in responses[:4]] == [
                {"remainingAttempts": n} for n in (4, 3, 2, 1)
            ]
            locked = responses[4].json()["error"]
            assert locked["code"] == "AUTH_LOCKED" and locked["detail"]["lockedUntil"].endswith("+09:00")
        real, unknown = results["real-lock@example.com"], results[unknown_email]
        assert [r.json()["error"].keys() for r in real] == [r.json()["error"].keys() for r in unknown]

    async def test_login_unknown_email_lock_then_unlock(self):
        """가입하지 않은 이메일도 잠김이 풀리면 1번째 실패부터 다시 셈"""
        email = f"nobody-{uuid.uuid4().hex[:8]}@example.com"
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            for _ in range(5):
                await client.post("/api/v1/auth/login", json={"email": email, "password": "wrong123"})
            locked = await client.post("/api/v1/auth/login", json={"email": email, "password": "wrong123"})
            await unknown_email_attempts.clear(email)  # 10분이 지난 것처럼
            again = await client.post("/api/v1/auth/login", json={"email": email, "password": "wrong123"})

        assert locked.status_code == status.HTTP_423_LOCKED
        assert again.json()["error"]["detail"] == {"remainingAttempts": 4}

    async def test_login_unknown_email_when_redis_down(self):
        """Redis가 꺼져도 가입하지 않은 이메일은 500이 아니라 회원 첫 실패와 같은 401 (서버 오류로 가입 여부가 드러나지 않게)"""
        email = f"nobody-{uuid.uuid4().hex[:8]}@example.com"
        with patch.object(unknown_email_attempts, "locked_until", side_effect=RedisConnectionError("down")):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post("/api/v1/auth/login", json={"email": email, "password": "wrong123"})

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json()["error"]["detail"] == {"remainingAttempts": 4}

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
