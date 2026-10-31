from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.apis.v1.auth_routers import REFRESH_COOKIE
from app.core import config
from app.dependencies.security import get_request_user
from app.dtos.users import (
    ConsentAgainRequest,
    ConsentItem,
    ConsentsResponse,
    UserInfoResponse,
    UserUpdateRequest,
    WithdrawRequest,
)
from app.models.users import User
from app.services.users import UserManageService

user_router = APIRouter(prefix="/users", tags=["users"])


@user_router.get("/me", response_model=UserInfoResponse, status_code=status.HTTP_200_OK)
async def user_me_info(
    user: Annotated[User, Depends(get_request_user)],
    user_manage_service: Annotated[UserManageService, Depends(UserManageService)],
) -> UserInfoResponse:
    """U-1"""
    profile = await user_manage_service.get_health_profile(user)
    return UserInfoResponse.from_user(user, profile)


@user_router.patch("/me", response_model=UserInfoResponse, status_code=status.HTTP_200_OK)
async def update_user_me_info(
    update_data: UserUpdateRequest,
    user: Annotated[User, Depends(get_request_user)],
    user_manage_service: Annotated[UserManageService, Depends(UserManageService)],
) -> UserInfoResponse:
    """U-2"""
    updated_user, profile = await user_manage_service.update_user(user=user, data=update_data)
    return UserInfoResponse.from_user(updated_user, profile)


@user_router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def withdraw_user_me(
    data: WithdrawRequest,
    user: Annotated[User, Depends(get_request_user)],
    user_manage_service: Annotated[UserManageService, Depends(UserManageService)],
) -> Response:
    """U-3 회원 탈퇴"""
    await user_manage_service.withdraw_user(user=user, confirmed=data.confirmed)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(key=REFRESH_COOKIE, domain=config.COOKIE_DOMAIN or None)
    return response


@user_router.get("/me/consents", response_model=ConsentsResponse, status_code=status.HTTP_200_OK)
async def user_consents(
    user: Annotated[User, Depends(get_request_user)],
    user_manage_service: Annotated[UserManageService, Depends(UserManageService)],
) -> ConsentsResponse:
    """U-4 동의 내역"""
    consents = await user_manage_service.list_consents(user)
    return ConsentsResponse(items=[ConsentItem.from_consent(c) for c in consents])


@user_router.put("/me/consents/{consent_type}", status_code=status.HTTP_204_NO_CONTENT)
async def agree_consent(
    consent_type: str,
    data: ConsentAgainRequest,
    user: Annotated[User, Depends(get_request_user)],
    user_manage_service: Annotated[UserManageService, Depends(UserManageService)],
) -> Response:
    """U-6 다시 동의 (sensitiveHealth만)"""
    await user_manage_service.agree_consent(user=user, type_name=consent_type, agreed=data.agreed)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@user_router.delete("/me/consents/{consent_type}", status_code=status.HTTP_204_NO_CONTENT)
async def withdraw_consent(
    consent_type: str,
    user: Annotated[User, Depends(get_request_user)],
    user_manage_service: Annotated[UserManageService, Depends(UserManageService)],
) -> Response:
    """U-5 동의 철회 (sensitiveHealth만)"""
    await user_manage_service.withdraw_consent(user=user, type_name=consent_type)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
