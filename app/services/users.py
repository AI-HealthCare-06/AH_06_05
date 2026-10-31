import secrets
from datetime import datetime

from starlette import status
from tortoise.transactions import in_transaction

from app.core import config
from app.core.errors import AppError
from app.dtos.users import CONSENT_TYPE_NAMES, UserUpdateRequest
from app.models.analysis import Analysis, GuideFeedback
from app.models.chat import ChatSession
from app.models.ocr import OcrJob, Prescription
from app.models.users import ConsentType, Sex, User, UserConsent, UserHealthProfile
from app.repositories.user_repository import UserRepository
from app.services import habits
from app.services.ocr import photos

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

    async def list_consents(self, user: User) -> list[UserConsent]:
        """U-4"""
        return await UserConsent.filter(user=user).order_by("id")

    async def withdraw_consent(self, user: User, type_name: str) -> None:
        """U-5. sensitiveHealth만 철회할 수 있음. 철회하면 건강 정보가 들어 있을 수 있는 기록을 지움.
        실천 목표는 끝내고 기록은 남김 (명세서 U-5 표). 추천(질환 라벨)은 분석과 같이 지워짐. 포인트는 서버에 아직 없음"""
        if type_name != CONSENT_TYPE_NAMES[ConsentType.SENSITIVE_HEALTH]:
            raise AppError(
                status.HTTP_400_BAD_REQUEST,
                "VALIDATION_ERROR",
                "건강 정보 동의만 철회할 수 있어요.",
                field="type",
            )
        consent = await UserConsent.get_or_none(user=user, consent_type=ConsentType.SENSITIVE_HEALTH)
        if consent is None or (not consent.agreed and consent.withdrawn_at is not None):
            return  # 이미 철회함 (다시 불러도 같은 결과)
        await _erase_health_records(user)
        await habits.end_goals(user)
        await UserConsent.filter(id=consent.id).update(agreed=False, withdrawn_at=datetime.now(config.TIMEZONE))

    async def withdraw_user(self, user: User, confirmed: bool) -> None:
        """U-3. 기록을 모두 바로 지우고, 사용자 줄은 개인정보를 지운 뒤 id와 deleted_at만 남김"""
        if confirmed is not True:
            raise AppError(status.HTTP_400_BAD_REQUEST, "VALIDATION_ERROR", "탈퇴를 확인해 주세요.", field="confirmed")
        await _erase_health_records(user)
        await habits.delete_goals(user)
        async with in_transaction():
            await UserConsent.filter(user=user).delete()
            # 이메일은 다시 가입할 수 있게 비움. 출생연도와 성별은 칸을 비울 수 없어서 자리 값(0, M)으로 채움
            await User.filter(id=user.id).update(
                login_id=f"withdrawn-{user.id}",
                password_hash=secrets.token_hex(32),
                birth_year=0,
                sex=Sex.M,
                failed_login_count=0,
                locked_until=None,
                deleted_at=datetime.now(config.TIMEZONE),
            )


async def _erase_health_records(user: User) -> None:
    """처방전 · OCR 작업과 사진 · 분석(경고 · 안내문 · 피드백) · 챗봇 대화 · 건강 정보를 지움 (U-3, U-5 공통).
    사진은 저장소에서 먼저 지움 (못 지운 사진은 저장소 규칙이 1일 뒤 지움). 파일 지문은 처방전과 같이 지워짐"""
    await photos.delete_user_photos(user.id)
    async with in_transaction():
        await ChatSession.filter(user=user).delete()  # 메시지는 DB가 같이 지움
        await GuideFeedback.filter(user=user).delete()
        await Analysis.filter(user=user).delete()
        await Prescription.filter(user=user).delete()
        await OcrJob.filter(user=user).delete()
        await UserHealthProfile.filter(user=user).delete()
