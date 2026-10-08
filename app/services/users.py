from app.dtos.users import UserUpdateRequest
from app.models.users import User
from app.repositories.user_repository import UserRepository


class UserManageService:
    def __init__(self):
        self.repo = UserRepository()

    async def update_user(self, user: User, data: UserUpdateRequest) -> User:
        """U-2. 보낸 칸만 바꿈. 출생연도 · 성별은 다음 분석부터 반영 (지난 결과는 다시 계산하지 않음)"""
        changes = data.model_dump(exclude_unset=True)
        for key in ("birth_year", "sex"):
            if key in changes and changes[key] is None:
                changes.pop(key)  # 필수 칸은 비울 수 없음 → 안 보낸 것으로
        await self.repo.update_instance(user=user, data=changes)
        return user
