from starlette import status

from app.core.errors import AppError
from app.dtos.users import UserUpdateRequest
from app.models.users import Sex, User, UserHealthProfile
from app.repositories.user_repository import UserRepository

REQUIRED_FIELDS = ("birth_year", "sex")
REQUIRED_HEALTH_FIELDS = ("smoking", "drinking")


class UserManageService:
    def __init__(self):
        self.repo = UserRepository()

    async def get_health_profile(self, user: User) -> UserHealthProfile:
        return await self.repo.get_health_profile(user)

    async def update_user(self, user: User, data: UserUpdateRequest) -> tuple[User, UserHealthProfile]:
        """U-2. 보낸 칸만 바꿈. 출생연도, 성별, 건강 정보는 다음 분석부터 반영 (지난 결과는 다시 계산하지 않음)"""
        changes = data.model_dump(exclude_unset=True)
        health = changes.pop("health", None) or {}
        for key in REQUIRED_FIELDS:
            if key in changes and changes[key] is None:
                changes.pop(key)  # 필수 칸은 비울 수 없음 → 안 보낸 것으로
        for key in REQUIRED_HEALTH_FIELDS:
            if key in health and health[key] is None:
                health.pop(key)

        profile = await self.repo.get_health_profile(user)
        sex = changes.get("sex", user.sex)
        if health.get("pregnant") is not None and sex != Sex.F:
            raise AppError(
                status.HTTP_400_BAD_REQUEST,
                "VALIDATION_ERROR",
                "임신 여부는 여성만 입력할 수 있어요.",
                field="health.pregnant",
            )
        if sex == Sex.M and profile.pregnant is not None:
            health["pregnant"] = None  # 성별을 M으로 바꾸면 임신 여부를 비움
        if "upcoming_exams" in health:
            health["upcoming_exams"] = [
                {"name": e["name"], "date": e["date"].isoformat()} for e in health["upcoming_exams"] or []
            ]
        if "diseases" in health and health["diseases"] is None:
            health["diseases"] = []

        await self.repo.update_user_and_health(user=user, user_data=changes, profile=profile, health_data=health)
        return user, profile
