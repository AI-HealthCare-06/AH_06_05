from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette import status

from app.core.errors import AppError
from app.models.users import User
from app.repositories.user_repository import UserRepository
from app.services.jwt import JwtService

security = HTTPBearer(auto_error=False)


async def get_request_user(
    credential: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
) -> User:
    """Authorization: Bearer {출입증}. 없거나 잘못되면 401 UNAUTHORIZED, 끝났으면 401 TOKEN_EXPIRED"""
    if credential is None:
        raise AppError(status.HTTP_401_UNAUTHORIZED, "UNAUTHORIZED")
    verified = JwtService().verify_jwt(token=credential.credentials, token_type="access")
    user = await UserRepository().get_user(verified.payload["user_id"])
    if not user:
        raise AppError(status.HTTP_401_UNAUTHORIZED, "UNAUTHORIZED")
    return user
