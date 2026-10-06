import time
from email.utils import parsedate_to_datetime

from httpx import ASGITransport, AsyncClient
from starlette import status
from tortoise.contrib.test import TestCase

from app.core.jwt.tokens import AccessToken, RefreshToken
from app.main import app


class TestLoginAPI(TestCase):
    async def test_login_success(self):
        # 먼저 사용자 등록
        signup_data = {
            "email": "login_test@example.com",
            "password": "Password123!",
            "name": "로그인테스터",
            "gender": "FEMALE",
            "birth_date": "1995-05-05",
            "phone_number": "01011112222",
        }
        login_data = {"email": "login_test@example.com", "password": "Password123!"}

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post("/api/v1/auth/signup", json=signup_data)

            # 로그인 시도
            response = await client.post("/api/v1/auth/login", json=login_data)
        assert response.status_code == status.HTTP_200_OK
        assert "access_token" in response.json()
        # 쿠키 검증 대신 응답 헤더 확인
        assert any("refresh_token" in header for header in response.headers.get_list("set-cookie"))

    async def test_login_invalid_credentials(self):
        login_data = {"email": "nonexistent@example.com", "password": "WrongPassword123!"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/auth/login", json=login_data)

        # AuthService.authenticate 에서 실패 시 HTTP_400_BAD_REQUEST 발생
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    async def test_login_refresh_token_lifetime(self):
        """재발급 토큰과 쿠키 만료가 설정값(14일)과 비슷해야 한다 (55년 · 57년으로 나오던 버그 방지)"""
        signup_data = {
            "email": "lifetime_test@example.com",
            "password": "Password123!",
            "name": "만료테스터",
            "gender": "FEMALE",
            "birth_date": "1995-05-05",
            "phone_number": "01033334444",
        }
        login_data = {"email": "lifetime_test@example.com", "password": "Password123!"}

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post("/api/v1/auth/signup", json=signup_data)
            response = await client.post("/api/v1/auth/login", json=login_data)

        cookie = next(h for h in response.headers.get_list("set-cookie") if h.startswith("refresh_token="))
        parts = [part.strip() for part in cookie.split(";")]
        token_value = parts[0].split("=", 1)[1]
        expires = next(part.split("=", 1)[1] for part in parts if part.lower().startswith("expires="))

        day = 24 * 60 * 60
        token_left = RefreshToken(token_value).payload["exp"] - time.time()
        cookie_left = parsedate_to_datetime(expires).timestamp() - time.time()

        # 14일 설정, 앞뒤로 하루씩 여유 (시간대 계산 오차 허용)
        assert 13 * day < token_left < 15 * day, f"재발급 토큰 만료까지 {token_left / day:.1f}일"
        assert 13 * day < cookie_left < 15 * day, f"재발급 쿠키 만료까지 {cookie_left / day:.1f}일"

    async def test_login_access_token_lifetime(self):
        """출입증(access) 토큰 만료가 설정값(60분)과 비슷해야 한다 (한국 시각을 UTC로 읽어 600분으로 나오던 버그 방지)"""
        signup_data = {
            "email": "access_lifetime_test@example.com",
            "password": "Password123!",
            "name": "출입증테스터",
            "gender": "FEMALE",
            "birth_date": "1995-05-05",
            "phone_number": "01055556666",
        }
        login_data = {"email": "access_lifetime_test@example.com", "password": "Password123!"}

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post("/api/v1/auth/signup", json=signup_data)
            response = await client.post("/api/v1/auth/login", json=login_data)

        access_token = response.json()["access_token"]
        minutes_left = (AccessToken(access_token).payload["exp"] - time.time()) / 60

        # 60분 설정, 앞뒤로 5분씩 여유
        assert 55 < minutes_left < 65, f"출입증 토큰 만료까지 {minutes_left:.1f}분"
