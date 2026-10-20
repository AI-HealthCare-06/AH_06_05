from datetime import datetime
from typing import Any

from tortoise.transactions import in_transaction

from app.core import config
from app.models.users import ConsentType, Drinking, Sex, Smoking, User, UserConsent, UserHealthProfile

UPDATED_AT_FIELD = "updated_at"


class UserRepository:
    def __init__(self):
        self._model = User

    async def get_user(self, user_id: int) -> User | None:
        """탈퇴한 회원(deleted_at)은 없는 회원으로 봄"""
        return await self._model.get_or_none(id=user_id, deleted_at=None)

    async def get_user_by_email(self, email: str) -> User | None:
        return await self._model.get_or_none(login_id=email, deleted_at=None)

    async def exists_by_email(self, email: str) -> bool:
        return await self._model.filter(login_id=email).exists()

    async def create_user_with_consents(
        self,
        *,
        email: str,
        password_hash: str,
        birth_year: int,
        sex: Sex,
        smoking: Smoking,
        drinking: Drinking,
        consents: dict[ConsentType, bool],
    ) -> User:
        """회원, 동의, 건강 정보를 한 번에 만듦 (건강 정보 줄은 가입 때 항상 생김)"""
        now = datetime.now(config.TIMEZONE)
        async with in_transaction():
            user = await self._model.create(
                login_id=email,
                password_hash=password_hash,
                birth_year=birth_year,
                sex=sex,
            )
            await UserConsent.bulk_create(
                [
                    UserConsent(user=user, consent_type=consent_type, agreed=agreed, agreed_at=now if agreed else None)
                    for consent_type, agreed in consents.items()
                ]
            )
            await UserHealthProfile.create(user=user, smoking=smoking, drinking=drinking)
        return user

    async def get_health_profile(self, user: User) -> UserHealthProfile:
        """건강 정보 표가 생기기 전에 가입한 회원은 줄이 없어서, 흡연과 음주를 "잘 모르겠어요"로 두고 만듦"""
        profile, _ = await UserHealthProfile.get_or_create(
            user=user, defaults={"smoking": Smoking.UNKNOWN, "drinking": Drinking.UNKNOWN}
        )
        return profile

    async def record_login_failure(self, user: User, *, lock_until: datetime | None) -> None:
        """틀린 횟수 +1. 잠그면 횟수는 0으로 되돌리고 잠금 시각을 넣음"""
        if lock_until is None:
            user.failed_login_count += 1
        else:
            user.failed_login_count = 0
        user.locked_until = lock_until
        await user.save(update_fields=["failed_login_count", "locked_until"])

    async def reset_login_failures(self, user: User) -> None:
        if user.failed_login_count or user.locked_until:
            user.failed_login_count = 0
            user.locked_until = None
            await user.save(update_fields=["failed_login_count", "locked_until"])

    async def update_user_and_health(
        self, user: User, user_data: dict[str, Any], profile: UserHealthProfile, health_data: dict[str, Any]
    ) -> None:
        """U-2: 회원 칸과 건강 정보 칸을 한 번에 바꿈"""
        async with in_transaction():
            await self.update_instance(user=user, data=user_data)
            if health_data:
                for key, value in health_data.items():
                    setattr(profile, key, value)
                await profile.save(update_fields=[*health_data.keys(), UPDATED_AT_FIELD])

    async def update_instance(self, user: User, data: dict[str, Any]) -> None:
        update_fields = list(data.keys())
        for key, value in data.items():
            setattr(user, key, value)
        if update_fields:
            user.updated_at = datetime.now(config.TIMEZONE)
            update_fields.append(UPDATED_AT_FIELD)
            await user.save(update_fields=update_fields)
