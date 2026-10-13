from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from redis.exceptions import RedisError
from starlette import status

from app.core import config
from app.core.errors import AppError
from app.core.logger import default_logger
from app.core.utils.security import hash_password, verify_password
from app.dtos.auth import LoginRequest, SignUpRequest
from app.models.users import LOCK_MINUTES, MAX_LOGIN_FAILURES, ConsentType, User
from app.repositories.user_repository import UserRepository
from app.services import unknown_email_attempts
from app.services.jwt import JwtService

INVALID_CREDENTIALS_MESSAGE = "이메일 또는 비밀번호가 맞지 않아요."
LOCKED_MESSAGE = f"비밀번호를 {MAX_LOGIN_FAILURES}번 틀려서 {LOCK_MINUTES}분 동안 로그인할 수 없어요."
_DUMMY_HASH = hash_password("timing-equalizer-not-a-real-password")  # 가입하지 않은 이메일일 때 비교용


@dataclass(frozen=True)
class IssuedTokens:
    access_token: str
    refresh_token: str
    refresh_expires_at: datetime  # 쿠키 만료를 재발급권과 맞춤


def _aware(value: datetime) -> datetime:
    """DB에서 시간대 없이 읽힌 값은 한국 시간으로 봄"""
    return value if value.tzinfo else value.replace(tzinfo=config.TIMEZONE)


class AuthService:
    def __init__(self):
        self.user_repo = UserRepository()
        self.jwt_service = JwtService()

    async def signup(self, data: SignUpRequest) -> User:
        # 필수 동의 3개 (A-1) — 빠진 첫 항목을 field로 알려 줌
        consents = {
            ConsentType.TERMS: data.consents.terms,
            ConsentType.PRIVACY: data.consents.privacy,
            ConsentType.SENSITIVE_HEALTH: data.consents.sensitive_health,
        }
        for field, agreed in (
            ("consents.terms", data.consents.terms),
            ("consents.privacy", data.consents.privacy),
            ("consents.sensitiveHealth", data.consents.sensitive_health),
        ):
            if not agreed:
                raise AppError(
                    status.HTTP_400_BAD_REQUEST, "CONSENT_REQUIRED", "필수 동의 항목에 모두 동의해 주세요.", field=field
                )

        email = str(data.email)
        if await self.user_repo.exists_by_email(email):
            raise AppError(status.HTTP_409_CONFLICT, "EMAIL_DUPLICATED", "이미 가입된 이메일이에요.", field="email")

        return await self.user_repo.create_user_with_consents(
            email=email,
            password_hash=hash_password(data.password),
            nickname=data.nickname,
            birth_year=data.birth_year,
            sex=data.sex,
            consents=consents,
        )

    async def authenticate(self, data: LoginRequest) -> User:
        """A-2. 이메일이 없을 때와 비밀번호가 틀렸을 때 같은 코드 · 문구로 응답"""
        user = await self.user_repo.get_user_by_email(str(data.email))
        now = datetime.now(config.TIMEZONE)
        if not user:
            raise await self._fail_unknown_email(str(data.email), data.password, now)

        if user.locked_until and _aware(user.locked_until) > now:
            raise self._locked_error(_aware(user.locked_until))

        if not verify_password(data.password, user.password_hash):
            failures = (0 if user.locked_until else user.failed_login_count) + 1
            if failures >= MAX_LOGIN_FAILURES:
                lock_until = now + timedelta(minutes=LOCK_MINUTES)
                await self.user_repo.record_login_failure(user, lock_until=lock_until)
                raise self._locked_error(lock_until)
            if user.locked_until:  # 지난 잠금은 지우고 1번째 실패부터 다시 셈
                user.failed_login_count = 0
            await self.user_repo.record_login_failure(user, lock_until=None)
            raise self._invalid_error(failures)

        await self.user_repo.reset_login_failures(user)
        return user

    async def _fail_unknown_email(self, email: str, password: str, now: datetime) -> AppError:
        """가입하지 않은 이메일도 가입한 회원과 같은 횟수, 같은 잠김, 비슷한 시간으로 실패시킴 (순서도 같게)"""
        try:
            until = await unknown_email_attempts.locked_until(email)
            if until and until > now:
                return self._locked_error(until)
            verify_password(
                password, _DUMMY_HASH
            )  # 회원과 같이 비밀번호 확인 시간이 들게 (응답 시간으로 드러나지 않게)
            failures, lock_until = await unknown_email_attempts.record_failure(
                email, max_failures=MAX_LOGIN_FAILURES, lock_minutes=LOCK_MINUTES, now=now
            )
        except RedisError:
            # Redis가 꺼져도 500이 아니라 회원 첫 실패와 같은 응답 (서버 오류로 가입 여부가 드러나지 않게)
            default_logger.warning("가입하지 않은 이메일의 로그인 실패를 Redis에 셀 수 없음")
            return self._invalid_error(1)
        return self._locked_error(lock_until) if lock_until else self._invalid_error(failures)

    @staticmethod
    def _invalid_error(failures: int) -> AppError:
        return AppError(
            status.HTTP_401_UNAUTHORIZED,
            "AUTH_INVALID_CREDENTIALS",
            INVALID_CREDENTIALS_MESSAGE,
            detail={"remainingAttempts": MAX_LOGIN_FAILURES - failures},
        )

    def issue_tokens(self, user: User) -> IssuedTokens:
        pair = self.jwt_service.issue_jwt_pair(user)
        return IssuedTokens(
            access_token=str(pair["access_token"]),
            refresh_token=str(pair["refresh_token"]),
            refresh_expires_at=datetime.fromtimestamp(pair["refresh_token"].payload["exp"], tz=UTC),
        )

    @staticmethod
    def _locked_error(locked_until: datetime) -> AppError:
        return AppError(
            status.HTTP_423_LOCKED,
            "AUTH_LOCKED",
            LOCKED_MESSAGE,
            detail={"lockedUntil": locked_until.astimezone(config.TIMEZONE).isoformat(timespec="seconds")},
        )
