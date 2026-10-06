from typing import Annotated

from fastapi import APIRouter, Body, Cookie, Depends, Response, status

from app.core import config
from app.core.config import Env
from app.core.errors import AppError
from app.dtos.auth import (
    AuthTokensResponse,
    LoginRequest,
    SignUpRequest,
    TokenRefreshRequest,
    TokenRefreshResponse,
    UserSummary,
)
from app.services.auth import AuthService, IssuedTokens
from app.services.jwt import JwtService

auth_router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "refresh_token"


def _tokens_response(response: Response, tokens: IssuedTokens, user_summary: UserSummary) -> AuthTokensResponse:
    """재발급권은 본문(앱 보안 저장소용)과 쿠키(웹 · Swagger 시험용) 둘 다로 줌"""
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=tokens.refresh_token,
        httponly=True,
        secure=config.ENV == Env.PROD,
        domain=config.COOKIE_DOMAIN or None,
        expires=tokens.refresh_expires_at,
    )
    return AuthTokensResponse(access_token=tokens.access_token, refresh_token=tokens.refresh_token, user=user_summary)


@auth_router.post("/signup", response_model=AuthTokensResponse, status_code=status.HTTP_201_CREATED)
async def signup(
    request: SignUpRequest,
    response: Response,
    auth_service: Annotated[AuthService, Depends(AuthService)],
) -> AuthTokensResponse:
    """A-1. 가입과 동시에 로그인 처리"""
    user = await auth_service.signup(request)
    return _tokens_response(response, auth_service.issue_tokens(user), UserSummary.model_validate(user))


@auth_router.post("/login", response_model=AuthTokensResponse, status_code=status.HTTP_200_OK)
async def login(
    request: LoginRequest,
    response: Response,
    auth_service: Annotated[AuthService, Depends(AuthService)],
) -> AuthTokensResponse:
    """A-2"""
    user = await auth_service.authenticate(request)
    return _tokens_response(response, auth_service.issue_tokens(user), UserSummary.model_validate(user))


@auth_router.post("/token/refresh", response_model=TokenRefreshResponse, status_code=status.HTTP_200_OK)
async def token_refresh(
    jwt_service: Annotated[JwtService, Depends(JwtService)],
    body: Annotated[TokenRefreshRequest | None, Body()] = None,
    refresh_token: Annotated[str | None, Cookie()] = None,
) -> TokenRefreshResponse:
    """A-4. 본문의 refreshToken을 먼저 보고, 없으면 쿠키를 봄. 재발급권은 새로 주지 않음"""
    token = (body.refresh_token if body else None) or refresh_token
    if not token:
        raise AppError(status.HTTP_401_UNAUTHORIZED, "UNAUTHORIZED")
    return TokenRefreshResponse(access_token=str(jwt_service.refresh_jwt(token)))
