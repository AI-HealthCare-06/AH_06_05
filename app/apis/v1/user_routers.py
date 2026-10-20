from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.dependencies.security import get_request_user
from app.dtos.users import UserInfoResponse, UserUpdateRequest
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
