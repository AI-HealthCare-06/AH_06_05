from httpx import ASGITransport, AsyncClient
from starlette import status
from tortoise.contrib.test import TestCase

from app.main import app
from app.models.users import User, UserHealthProfile
from app.tests.helpers import signup

EMPTY_HEALTH = {
    "smoking": "never",
    "drinking": "monthly",
    "diseases": [],
    "pregnant": None,
    "dialysis": None,
    "heightCm": None,
    "weightKg": None,
    "upcomingExams": [],
}


async def _headers(client: AsyncClient, email: str, **overrides) -> dict[str, str]:
    tokens = await signup(client, email, **overrides)
    return {"Authorization": f"Bearer {tokens['accessToken']}"}


class TestUserMeApis(TestCase):
    async def test_get_user_me(self):
        """U-1: camelCase, 이메일은 로그인 아이디, 별명 없음(#96), 건강 정보(#101)"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/users/me", headers=await _headers(client, "me@example.com"))
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert set(body) == {"id", "email", "birthYear", "sex", "createdAt", "health"}
        assert body["email"] == "me@example.com"
        assert body["birthYear"] == 1958 and body["sex"] == "M"
        assert body["health"] == EMPTY_HEALTH

    async def test_update_user_me_only_sent_fields(self):
        """U-2: 보낸 칸만 바뀜"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = await _headers(client, "update@example.com")
            response = await client.patch("/api/v1/users/me", json={"birthYear": 1960}, headers=headers)
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["birthYear"] == 1960 and body["sex"] == "M" and body["health"] == EMPTY_HEALTH

    async def test_update_health_only_sent_fields(self):
        """U-2: health 안에서도 보낸 칸만 바뀌고, 목록 칸은 보낸 목록으로 통째로 바뀜"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = await _headers(client, "health@example.com")
            first = await client.patch(
                "/api/v1/users/me",
                json={
                    "health": {
                        "diseases": ["HTN", "CKD"],
                        "dialysis": "no",
                        "heightCm": 165,
                        "weightKg": 62.5,
                        "upcomingExams": [{"name": "조영 CT", "date": "2026-10-27"}],
                    }
                },
                headers=headers,
            )
            second = await client.patch(
                "/api/v1/users/me", json={"health": {"drinking": "none", "diseases": ["DM2"]}}, headers=headers
            )
        assert first.status_code == status.HTTP_200_OK, first.text
        assert second.status_code == status.HTTP_200_OK, second.text
        assert second.json()["health"] == {
            "smoking": "never",
            "drinking": "none",
            "diseases": ["DM2"],
            "pregnant": None,
            "dialysis": "no",
            "heightCm": 165,
            "weightKg": 62.5,
            "upcomingExams": [{"name": "조영 CT", "date": "2026-10-27"}],
        }

    async def test_pregnant_only_for_women_and_cleared_when_sex_becomes_m(self):
        """U-2: 임신 여부는 여성만. 성별을 M으로 바꾸면 비움"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            male = await _headers(client, "male@example.com")
            rejected = await client.patch("/api/v1/users/me", json={"health": {"pregnant": "no"}}, headers=male)
            female = await _headers(client, "female@example.com", sex="F")
            saved = await client.patch("/api/v1/users/me", json={"health": {"pregnant": "yes"}}, headers=female)
            both = await client.patch(
                "/api/v1/users/me", json={"sex": "M", "health": {"pregnant": "no"}}, headers=female
            )
            changed = await client.patch("/api/v1/users/me", json={"sex": "M"}, headers=female)
        assert rejected.status_code == status.HTTP_400_BAD_REQUEST
        assert rejected.json()["error"]["code"] == "VALIDATION_ERROR"
        assert rejected.json()["error"]["field"] == "health.pregnant"
        assert saved.json()["health"]["pregnant"] == "yes"
        assert both.status_code == status.HTTP_400_BAD_REQUEST  # 바뀐 성별 기준으로 판단
        assert changed.status_code == status.HTTP_200_OK
        assert changed.json()["sex"] == "M" and changed.json()["health"]["pregnant"] is None

    async def test_update_health_validation(self):
        """U-2: 질환 id, 값 목록, 키와 몸무게, 예정 검사 이름 50자와 날짜 모양"""
        cases = [
            ({"diseases": ["I10"]}, "health.diseases.0"),
            ({"smoking": "yes"}, "health.smoking"),
            ({"dialysis": "maybe"}, "health.dialysis"),
            ({"heightCm": 0}, "health.heightCm"),
            ({"weightKg": 62.55}, "health.weightKg"),
            ({"upcomingExams": [{"name": "가" * 51, "date": "2026-10-27"}]}, "health.upcomingExams.0.name"),
            ({"upcomingExams": [{"name": "CT", "date": "10월 27일"}]}, "health.upcomingExams.0.date"),
            ({"unknownField": 1}, "health.unknownField"),
        ]
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = await _headers(client, "invalid@example.com")
            for health, field in cases:
                response = await client.patch("/api/v1/users/me", json={"health": health}, headers=headers)
                assert response.status_code == status.HTTP_400_BAD_REQUEST, health
                error = response.json()["error"]
                assert error["code"] == "VALIDATION_ERROR" and error["field"] == field, (health, error)

    async def test_update_user_me_rejects_email_and_nickname(self):
        """U-2: email은 바꿀 수 없고 별명은 없어진 칸 → VALIDATION_ERROR"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = await _headers(client, "noemail@example.com")
            email = await client.patch("/api/v1/users/me", json={"email": "x@example.com"}, headers=headers)
            nickname = await client.patch("/api/v1/users/me", json={"nickname": "길동"}, headers=headers)
        assert email.status_code == status.HTTP_400_BAD_REQUEST
        assert email.json()["error"]["code"] == "VALIDATION_ERROR" and email.json()["error"]["field"] == "email"
        assert nickname.status_code == status.HTTP_400_BAD_REQUEST
        assert nickname.json()["error"]["field"] == "nickname"

    async def test_member_without_health_row_gets_unknown(self):
        """건강 정보 표가 생기기 전에 가입한 회원: U-1, U-2가 500 없이 흡연과 음주를 "잘 모르겠어요"로 보여 줌"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = await _headers(client, "old@example.com")
            await UserHealthProfile.filter(user=await User.get(login_id="old@example.com")).delete()
            got = await client.get("/api/v1/users/me", headers=headers)
            patched = await client.patch("/api/v1/users/me", json={"health": {"dialysis": "no"}}, headers=headers)
        assert got.status_code == status.HTTP_200_OK
        assert got.json()["health"] == {**EMPTY_HEALTH, "smoking": "unknown", "drinking": "unknown"}
        assert patched.status_code == status.HTTP_200_OK and patched.json()["health"]["dialysis"] == "no"

    async def test_get_user_me_unauthorized(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/users/me")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json() == {"error": {"code": "UNAUTHORIZED", "message": "로그인이 필요해요."}}
