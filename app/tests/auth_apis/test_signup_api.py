from httpx import ASGITransport, AsyncClient
from starlette import status
from tortoise.contrib.test import TestCase

from app.main import app
from app.models.users import ConsentType, User, UserConsent
from app.tests.helpers import signup_payload


class TestSignupAPI(TestCase):
    async def test_signup_returns_tokens_and_user(self):
        """A-1: 가입과 동시에 로그인 — 출입증 · 재발급권 · 내 정보 (camelCase)"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/auth/signup", json=signup_payload("signup@example.com"))

        assert response.status_code == status.HTTP_201_CREATED
        body = response.json()
        assert set(body) == {"accessToken", "refreshToken", "user"}
        assert body["user"] == {"id": body["user"]["id"], "nickname": "홍길동", "birthYear": 1958, "sex": "M"}
        assert any(h.startswith("refresh_token=") for h in response.headers.get_list("set-cookie"))

        user = await User.get(login_id="signup@example.com")
        assert user.password_hash != "abcd1234"  # 해시로 저장
        consents = {c.consent_type: c.agreed for c in await UserConsent.filter(user=user)}
        assert consents == {ConsentType.TERMS: True, ConsentType.PRIVACY: True, ConsentType.SENSITIVE_HEALTH: True}

    async def test_signup_nickname_optional(self):
        payload = signup_payload("nonick@example.com")
        del payload["nickname"]
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/auth/signup", json=payload)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["user"]["nickname"] is None

    async def test_signup_duplicated_email(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post("/api/v1/auth/signup", json=signup_payload("dup@example.com"))
            response = await client.post("/api/v1/auth/signup", json=signup_payload("dup@example.com"))
        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.json() == {
            "error": {"code": "EMAIL_DUPLICATED", "message": "이미 가입된 이메일이에요.", "field": "email"}
        }

    async def test_signup_consent_required(self):
        payload = signup_payload(
            "noconsent@example.com", consents={"terms": True, "privacy": True, "sensitiveHealth": False}
        )
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/auth/signup", json=payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        error = response.json()["error"]
        assert error["code"] == "CONSENT_REQUIRED"
        assert error["field"] == "consents.sensitiveHealth"
        assert not await User.exists(login_id="noconsent@example.com")

    async def test_signup_validation_errors(self):
        """VALIDATION_ERROR + 어느 칸인지 (field) + 화면에 띄울 문장"""
        cases = [
            (signup_payload("bad-email"), "email"),
            (signup_payload("pw@example.com", password="abcdefgh"), "password"),  # 숫자 없음
            (signup_payload("pw2@example.com", password="abc123"), "password"),  # 8자 미만
            (signup_payload("year@example.com", birthYear=1899), "birthYear"),
            (signup_payload("sex@example.com", sex="X"), "sex"),
        ]
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            for payload, field in cases:
                response = await client.post("/api/v1/auth/signup", json=payload)
                assert response.status_code == status.HTTP_400_BAD_REQUEST, payload
                error = response.json()["error"]
                assert error["code"] == "VALIDATION_ERROR"
                assert error["field"] == field
                assert error["message"]
            response = await client.post(
                "/api/v1/auth/signup", json=signup_payload("pw3@example.com", password="abcdefgh")
            )
        assert response.json()["error"]["message"] == "비밀번호는 영문과 숫자를 섞어 8자 이상으로 만들어 주세요."
