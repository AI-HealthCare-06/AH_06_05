"""U-3 회원 탈퇴 · U-4 동의 내역 · U-5 동의 철회 (명세서 2장, 10/6 확정 파기 범위)"""

import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import boto3
from httpx import ASGITransport, AsyncClient
from moto import mock_aws
from starlette import status
from tortoise.contrib.test import TestCase

from app.core import config
from app.main import app
from app.models.analysis import Analysis, AnalysisStatus
from app.models.chat import ChatMessage, ChatSession, MessageRole
from app.models.ocr import DocType, MatchStatus, OcrJob, Prescription, PrescriptionFileHash, PrescriptionItem
from app.models.users import ConsentType, User, UserConsent, UserHealthProfile
from app.services import prescriptions as rx_svc
from app.services import unknown_email_attempts
from app.services.ocr import photo_store, photos
from app.services.prescriptions import Blob
from app.tests.helpers import PASSWORD, signup
from app.tests.ocr_apis.test_ocr_apis import JPG


class WithdrawCase(TestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        for name, value in (("PHOTO_DISK_DIR", str(self.tmp)), ("PHOTO_STORAGE", "disk")):
            patcher = patch.object(config, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    @staticmethod
    def client() -> AsyncClient:
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    async def member(self, client: AsyncClient, email: str) -> tuple[User, dict[str, str]]:
        tokens = await signup(client, email)
        return await User.get(login_id=email), {"Authorization": f"Bearer {tokens['accessToken']}"}

    async def fill(self, user: User) -> dict[str, int]:
        """건강 정보가 들어 있을 수 있는 기록을 한 벌 만들어 둠 (처방전, 사진, 파일 지문, 분석, 챗봇 대화)"""
        job = await OcrJob.create(user=user, file_count=1)
        await photos.save_job_photos(job.id, user.id, [Blob(1, b"photo", "jpg", "p1")])
        rx = await Prescription.create(user=user, ocr_job=job, file_index=0, doc_type=DocType.PRESCRIPTION)
        await PrescriptionFileHash.create(user=user, prescription=rx, file_hash="a" * 64)
        analysis = await Analysis.create(user=user, status=AnalysisStatus.DONE)
        item = await PrescriptionItem.create(prescription=rx, raw_name="약", match_status=MatchStatus.UNMATCHED)
        session = await ChatSession.create(user=user, analysis=analysis)
        message = await ChatMessage.create(session=session, role=MessageRole.USER, content="질문")
        return {"job": job.id, "rx": rx.id, "analysis": analysis.id, "item": item.id, "message": message.id}

    async def assert_erased(self, user: User, ids: dict[str, int]):
        assert not await OcrJob.filter(id=ids["job"]).exists()
        assert not await Prescription.filter(id=ids["rx"]).exists()
        assert not await PrescriptionFileHash.filter(user_id=user.id).exists()  # 파일 지문도 같이
        assert not await Analysis.filter(user_id=user.id).exists()
        assert not await ChatSession.filter(user_id=user.id).exists()
        assert not await UserHealthProfile.filter(user_id=user.id).exists()
        assert not await PrescriptionItem.filter(id=ids["item"]).exists()
        assert not await ChatMessage.filter(id=ids["message"]).exists()
        assert not self.stored_photos()  # 저장소의 사진도 바로 지움
        # user_id 칸이 있는 모든 표에 이 사용자의 줄이 남지 않음 (동의 기록은 호출하는 쪽에서 따로 봄)
        rows = await User._meta.db.execute_query_dict(
            "SELECT table_name FROM information_schema.columns "
            "WHERE column_name = 'user_id' AND table_schema = current_schema()"
        )
        for table in {r["table_name"] for r in rows} - {"user_consents"}:
            left = await User._meta.db.execute_query_dict(f'SELECT 1 FROM "{table}" WHERE user_id = $1', [user.id])
            assert not left, table

    def stored_photos(self) -> list:
        return list(self.tmp.rglob("*.jpg"))


class TestConsentsApi(WithdrawCase):
    async def test_list_consents(self):
        """U-4: 가입 때 동의한 세 개가 camelCase로 나옴"""
        async with self.client() as client:
            _, headers = await self.member(client, "c1@example.com")
            response = await client.get("/api/v1/users/me/consents", headers=headers)
        assert response.status_code == status.HTTP_200_OK
        items = response.json()["items"]
        assert [i["type"] for i in items] == ["terms", "privacy", "sensitiveHealth"]
        assert all(i["agreed"] and i["agreedAt"] and i["withdrawnAt"] is None for i in items)

    async def test_requires_login(self):
        async with self.client() as client:
            assert (await client.get("/api/v1/users/me/consents")).status_code == status.HTTP_401_UNAUTHORIZED
            response = await client.delete("/api/v1/users/me/consents/sensitiveHealth")
            assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestWithdrawConsent(WithdrawCase):
    async def test_withdraw_erases_records_and_blocks_upload_and_analysis(self):
        """U-5: 건강 정보 기록은 지우고, 동의 기록은 철회 시각과 함께 남기고, 업로드 · 분석은 403"""
        async with self.client() as client:
            user, headers = await self.member(client, "w1@example.com")
            ids = await self.fill(user)
            response = await client.delete("/api/v1/users/me/consents/sensitiveHealth", headers=headers)
            assert response.status_code == status.HTTP_204_NO_CONTENT
            await self.assert_erased(user, ids)

            consent = await UserConsent.get(user=user, consent_type=ConsentType.SENSITIVE_HEALTH)
            assert consent.agreed is False and consent.withdrawn_at is not None and consent.agreed_at is not None
            assert await UserConsent.filter(user=user, agreed=True).count() == 2  # 이용약관, 개인정보는 그대로

            upload = await client.post(
                "/api/v1/prescriptions", files=[("files", ("p.jpg", JPG, "image/jpeg"))], headers=headers
            )
            assert upload.status_code == status.HTTP_403_FORBIDDEN
            assert upload.json()["error"]["code"] == "CONSENT_REQUIRED"
            start = await client.post("/api/v1/analyses", json={"prescriptionIds": [ids["rx"]]}, headers=headers)
            assert start.status_code == status.HTTP_403_FORBIDDEN
            assert start.json()["error"]["code"] == "CONSENT_REQUIRED"

            listed = (await client.get("/api/v1/users/me/consents", headers=headers)).json()["items"]
            health = next(i for i in listed if i["type"] == "sensitiveHealth")
            assert health["agreed"] is False and health["withdrawnAt"]

    async def test_withdraw_twice_is_fine(self):
        async with self.client() as client:
            _, headers = await self.member(client, "w2@example.com")
            for _ in range(2):
                response = await client.delete("/api/v1/users/me/consents/sensitiveHealth", headers=headers)
                assert response.status_code == status.HTTP_204_NO_CONTENT

    async def test_only_sensitive_health_can_be_withdrawn(self):
        async with self.client() as client:
            user, headers = await self.member(client, "w3@example.com")
            for name in ("terms", "privacy", "nothing"):
                response = await client.delete(f"/api/v1/users/me/consents/{name}", headers=headers)
                assert response.status_code == status.HTTP_400_BAD_REQUEST
                assert response.json()["error"]["code"] == "VALIDATION_ERROR"
                assert response.json()["error"]["field"] == "type"
        assert await UserConsent.filter(user=user, agreed=True).count() == 3

    async def test_other_users_records_stay(self):
        async with self.client() as client:
            _, headers = await self.member(client, "w4@example.com")
            other, _ = await self.member(client, "w5@example.com")
            ids = await self.fill(other)
            await client.delete("/api/v1/users/me/consents/sensitiveHealth", headers=headers)
        assert await Prescription.filter(id=ids["rx"]).exists()
        assert await UserHealthProfile.filter(user_id=other.id).exists()
        assert self.stored_photos()


class TestWithdrawUser(WithdrawCase):
    async def delete_me(self, client: AsyncClient, headers: dict[str, str], body):
        return await client.request("DELETE", "/api/v1/users/me", json=body, headers=headers)

    async def test_withdraw_erases_everything_and_keeps_only_id_and_deleted_at(self):
        async with self.client() as client:
            await unknown_email_attempts.clear(
                "u1@example.com"
            )  # 앞서 돌린 시험의 틀린 로그인 횟수가 Redis에 남아 있을 수 있음
            self.addAsyncCleanup(unknown_email_attempts.clear, "u1@example.com")
            user, headers = await self.member(client, "u1@example.com")
            ids = await self.fill(user)
            response = await self.delete_me(client, headers, {"confirmed": True})
            assert response.status_code == status.HTTP_204_NO_CONTENT
            assert 'refresh_token=""' in response.headers.get("set-cookie", "")  # 재발급권 쿠키를 지움
            await self.assert_erased(user, ids)
            assert self.stored_photos() == []

            row = await User.get(id=user.id)
            assert row.deleted_at is not None
            assert row.login_id != "u1@example.com" and "u1" not in row.login_id  # 이메일을 지움
            assert row.birth_year == 0
            assert not await UserConsent.filter(user_id=user.id).exists()  # 동의 기록도 지움

            # 탈퇴한 뒤에는 출입증이 있어도 없는 회원
            assert (await client.get("/api/v1/users/me", headers=headers)).status_code == status.HTTP_401_UNAUTHORIZED
            login = await client.post("/api/v1/auth/login", json={"email": "u1@example.com", "password": PASSWORD})
            assert login.status_code == status.HTTP_401_UNAUTHORIZED

            # 같은 이메일로 다시 가입할 수 있음
            again = await client.post(
                "/api/v1/auth/signup",
                json={
                    "email": "u1@example.com",
                    "password": PASSWORD,
                    "birthYear": 1958,
                    "sex": "M",
                    "health": {"smoking": "never", "drinking": "monthly"},
                    "consents": {"terms": True, "privacy": True, "sensitiveHealth": True},
                },
            )
            assert again.status_code == status.HTTP_201_CREATED

    async def test_confirmed_must_be_true(self):
        async with self.client() as client:
            user, headers = await self.member(client, "u2@example.com")
            for body in ({"confirmed": False}, {}):
                response = await self.delete_me(client, headers, body)
                assert response.status_code == status.HTTP_400_BAD_REQUEST
                assert response.json()["error"]["code"] == "VALIDATION_ERROR"
            no_body = await client.delete("/api/v1/users/me", headers=headers)
            assert no_body.status_code == status.HTTP_400_BAD_REQUEST
        assert (await User.get(id=user.id)).deleted_at is None

    async def test_other_users_stay(self):
        async with self.client() as client:
            _, headers = await self.member(client, "u3@example.com")
            other, _ = await self.member(client, "u4@example.com")
            ids = await self.fill(other)
            await self.delete_me(client, headers, {"confirmed": True})
        assert await Prescription.filter(id=ids["rx"]).exists()
        assert (await User.get(id=other.id)).deleted_at is None
        assert await UserConsent.filter(user_id=other.id).count() == 3


class TestWithdrawWithS3(TestWithdrawUser):
    """사진이 S3에 있을 때도 탈퇴하면 S3에서 지워짐 (운영 설정)"""

    BUCKET = "ah06-withdraw-photos"
    REGION = "ap-northeast-2"

    async def asyncSetUp(self):
        await super().asyncSetUp()
        env = patch.dict(
            os.environ,
            {"AWS_ACCESS_KEY_ID": "test", "AWS_SECRET_ACCESS_KEY": "test", "AWS_DEFAULT_REGION": self.REGION},
        )
        env.start()
        self.addCleanup(env.stop)
        for name, value in (
            ("PHOTO_STORAGE", "s3"),
            ("PHOTO_S3_BUCKET", self.BUCKET),
            ("PHOTO_S3_REGION", self.REGION),
        ):
            patcher = patch.object(config, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        mock = mock_aws()
        mock.start()
        self.addCleanup(mock.stop)
        photo_store._s3_client.cache_clear()
        self.addCleanup(photo_store._s3_client.cache_clear)
        self.s3 = boto3.client("s3", region_name=self.REGION)
        self.s3.create_bucket(Bucket=self.BUCKET, CreateBucketConfiguration={"LocationConstraint": self.REGION})

    def stored_photos(self) -> list:
        return self.s3.list_objects_v2(Bucket=self.BUCKET).get("Contents", [])


class TestWithdrawWhileWorking(WithdrawCase):
    """업로드나 읽기가 진행 중일 때 탈퇴해도 지운 뒤에 기록이나 사진이 다시 생기지 않음"""

    async def test_photos_uploaded_after_withdraw_are_removed(self):
        async with self.client() as client:
            user, headers = await self.member(client, "late1@example.com")
            job = await OcrJob.create(user=user, file_count=1)
            saved = await photos.upload_job_photos(job.id, user.id, [Blob(1, b"late", "jpg", "p1")])  # 업로드 끝나기 전
            assert (
                await client.request("DELETE", "/api/v1/users/me", json={"confirmed": True}, headers=headers)
            ).status_code == 204
            assert self.stored_photos()  # 탈퇴 때는 아직 위치를 적기 전이라 사진이 남아 있음
            await photos.record_job_photos(job.id, saved)  # 업로드가 끝나고 위치를 적으려는 순간
        assert not self.stored_photos()

    async def test_run_job_after_withdraw_reads_nothing(self):
        async with self.client() as client:
            user, headers = await self.member(client, "late2@example.com")
            job = await OcrJob.create(user=user, file_count=1)
            await client.request("DELETE", "/api/v1/users/me", json={"confirmed": True}, headers=headers)
        read = AsyncMock()
        with patch.object(rx_svc, "_read_file", read):
            assert await rx_svc.run_job(job.id, user.id, [Blob(1, b"x" * 50, "jpg", "p1")]) is False
        read.assert_not_awaited()
        assert not await Prescription.filter(user_id=user.id).exists()

    async def test_run_job_stops_when_job_is_erased_midway(self):
        async with self.client() as client:
            user, headers = await self.member(client, "late3@example.com")
        job = await OcrJob.create(user=user, file_count=2)

        async def erase_then_read(*args, **kwargs):  # 첫 사진을 읽는 사이에 탈퇴
            await OcrJob.filter(id=job.id).delete()
            return None

        blobs = [Blob(i, b"%d" % i * 50, "jpg", f"p{i}") for i in (1, 2)]
        calls = AsyncMock(side_effect=erase_then_read)
        with (
            patch.object(rx_svc, "_read_file", calls),
            patch.object(rx_svc, "get_matcher", AsyncMock()),
            patch.object(rx_svc, "get_codes", AsyncMock()),
            patch.object(
                rx_svc.precheck,
                "screen",
                lambda b: type(
                    "S",
                    (),
                    {
                        "too_small": set(),
                        "ready": b,
                        "hashes": {x.file_index: f"h{x.file_index}" for x in b},
                        "duplicates": {},
                    },
                )(),
            ),
        ):
            try:
                await rx_svc.run_job(job.id, user.id, blobs)
            except Exception:
                pass
        assert calls.await_count == 1  # 두 번째 사진은 부르지 않음
