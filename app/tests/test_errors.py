from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from starlette import status
from tortoise.contrib.test import TestCase

from app.core.errors import register_error_handlers


def _make_app() -> FastAPI:
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/forbidden")
    async def forbidden():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    @app.get("/unauthorized")
    async def unauthorized():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    return app


class TestHttpErrorCodes(TestCase):
    async def _get(self, path: str):
        async with AsyncClient(transport=ASGITransport(app=_make_app()), base_url="http://test") as client:
            return await client.get(path)

    async def test_forbidden_is_not_unauthorized(self):
        """403은 UNAUTHORIZED가 아니라 FORBIDDEN — 앱이 UNAUTHORIZED를 받으면 로그인 화면으로 보내서 로그아웃처럼 보임"""
        response = await self._get("/forbidden")
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.json() == {"error": {"code": "FORBIDDEN", "message": "이 내용은 볼 수 없어요."}}

    async def test_unauthorized_stays_unauthorized(self):
        response = await self._get("/unauthorized")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json()["error"]["code"] == "UNAUTHORIZED"
