"""처방전 사진 임시 저장 — 저장소(디스크 · S3), 작업 시작 때(응답 뒤) 저장, 24시간 뒤 삭제, 사용자 사진 전체 삭제 (10/22 결정 1, 2)"""

import asyncio
import json
import os
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch

import boto3
from botocore.exceptions import ClientError
from moto import mock_aws
from starlette import status
from tortoise.contrib.test import TestCase

from app.core import config
from app.models.ocr import OcrJob
from app.models.users import ConsentType, Sex, User, UserConsent
from app.services import prescriptions as svc
from app.services.ocr import clova, photo_store, photos
from app.services.prescriptions import Blob
from app.tests.ocr_apis.test_ocr_apis import OcrApiCase, jpeg_of_size

KEY = "ocr/3/12/1.jpg"


class FakeS3:
    """boto3 S3 클라이언트 대신 — 호출만 기록하고 메모리에 저장"""

    def __init__(self):
        self.objects: dict[tuple[str, str], bytes] = {}
        self.calls: list[tuple] = []

    def put_object(self, *, Bucket, Key, Body, ContentType):  # noqa: N803 (boto3 인자 이름)
        self.calls.append(("put", Bucket, Key, ContentType))
        self.objects[(Bucket, Key)] = Body

    def get_object(self, *, Bucket, Key):  # noqa: N803
        self.calls.append(("get", Bucket, Key))

        class Body:
            def __init__(self, data):
                self.data = data

            def read(self):
                return self.data

        return {"Body": Body(self.objects[(Bucket, Key)])}

    def delete_object(self, *, Bucket, Key):  # noqa: N803
        self.calls.append(("delete", Bucket, Key))
        self.objects.pop((Bucket, Key), None)


class TestPhotoStore(TestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        for name, value in (("PHOTO_DISK_DIR", str(self.tmp)), ("PHOTO_S3_BUCKET", "bucket-x")):
            patcher = patch.object(config, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    async def test_off_by_default_and_refuses_to_store(self):
        with patch.object(config, "PHOTO_STORAGE", ""):
            assert photo_store.enabled() is False
            with self.assertRaises(photo_store.PhotoStoreError):
                await photo_store.put(KEY, b"x")

    async def test_setting_is_read_without_case_or_spaces_and_unknown_value_means_off(self):
        for value, expected in (("S3", True), (" disk ", True), ("", False), ("s33", False), ("true", False)):
            with patch.object(config, "PHOTO_STORAGE", value):
                assert photo_store.enabled() is expected, value
        with patch.object(config, "PHOTO_STORAGE", "bogus"), self.assertLogs(photo_store.logger, "WARNING"):
            assert photo_store.enabled() is False  # 오타는 경고를 남김

    async def test_disk_put_get_delete_and_cleans_empty_folders(self):
        with patch.object(config, "PHOTO_STORAGE", "disk"):
            await photo_store.put(KEY, b"abc")
            assert (self.tmp / KEY).read_bytes() == b"abc"
            assert await photo_store.get(KEY) == b"abc"
            await photo_store.delete(KEY)
            await photo_store.delete(KEY)  # 이미 없어도 오류가 아님
        assert not (self.tmp / "ocr" / "3").exists()  # 비어 있는 사용자 · 작업 폴더는 남기지 않음

    async def test_keys_outside_the_expected_shape_are_refused(self):
        with patch.object(config, "PHOTO_STORAGE", "disk"):
            for bad in ("../x.jpg", "ocr/3/12/../../1.jpg", "ocr/a/1/1.jpg", "/etc/passwd", "ocr/3/12/1.exe"):
                with self.assertRaises(photo_store.PhotoStoreError):
                    await photo_store.put(bad, b"x")
        assert list(self.tmp.iterdir()) == []

    async def test_s3_uses_bucket_and_content_type_without_access_keys(self):
        fake = FakeS3()
        with patch.object(config, "PHOTO_STORAGE", "s3"), patch.object(photo_store, "_s3_client", lambda: fake):
            await photo_store.put(KEY, b"abc")
            assert await photo_store.get(KEY) == b"abc"
            await photo_store.delete(KEY)
        assert fake.calls == [
            ("put", "bucket-x", KEY, "image/jpeg"),
            ("get", "bucket-x", KEY),
            ("delete", "bucket-x", KEY),
        ]
        assert fake.objects == {}

    async def test_s3_without_bucket_or_with_failing_client_raises_store_error(self):
        class Broken:
            def put_object(self, **kw):
                raise ConnectionError("secret-host.example")

        with patch.object(config, "PHOTO_STORAGE", "s3"), patch.object(photo_store, "_s3_client", lambda: Broken()):
            with self.assertRaises(photo_store.PhotoStoreError) as cm:
                await photo_store.put(KEY, b"x")
            assert "secret-host" not in str(cm.exception)  # 예외 종류만 남김
            with patch.object(config, "PHOTO_S3_BUCKET", ""), self.assertRaises(photo_store.PhotoStoreError):
                await photo_store.get(KEY)


class TestPhotoLifecycle(TestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        for name, value in (("PHOTO_DISK_DIR", str(self.tmp)), ("PHOTO_STORAGE", "disk")):
            patcher = patch.object(config, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.user = await User.create(login_id="ph1@example.com", password_hash="x", birth_year=1950, sex=Sex.F)
        self.other = await User.create(login_id="ph2@example.com", password_hash="x", birth_year=1950, sex=Sex.F)

    async def job_with_photos(self, user: User, hours_ago: float, n: int = 2) -> OcrJob:
        job = await OcrJob.create(user=user, file_count=n)
        await photos.save_job_photos(job.id, user.id, [Blob(i, b"p%d" % i, "jpg", f"p{i}") for i in range(1, n + 1)])
        await OcrJob.filter(id=job.id).update(created_at=datetime.now(UTC) - timedelta(hours=hours_ago))
        return await OcrJob.get(id=job.id)

    async def test_save_records_keys_only(self):
        job = await self.job_with_photos(self.user, 0)
        assert job.photos == [
            {"fileIndex": 1, "key": f"ocr/{self.user.id}/{job.id}/1.jpg"},
            {"fileIndex": 2, "key": f"ocr/{self.user.id}/{job.id}/2.jpg"},
        ]
        assert (self.tmp / job.photos[0]["key"]).read_bytes() == b"p1"

    async def test_failed_save_removes_what_was_saved_and_records_nothing(self):
        job = await OcrJob.create(user=self.user, file_count=2)
        real_put = photo_store.put

        async def flaky(key, content):
            if key.endswith("/2.jpg"):
                raise photo_store.PhotoStoreError("boom")
            await real_put(key, content)

        with patch.object(photo_store, "put", flaky), self.assertRaises(photo_store.PhotoStoreError):
            await photos.save_job_photos(job.id, self.user.id, [Blob(1, b"a", "jpg", "a"), Blob(2, b"b", "jpg", "b")])
        assert (await OcrJob.get(id=job.id)).photos is None
        assert list(self.tmp.rglob("*.jpg")) == []

    async def test_purge_deletes_only_photos_older_than_24_hours(self):
        old = await self.job_with_photos(self.user, 25)
        fresh = await self.job_with_photos(self.user, 23)
        assert await photos.purge_expired() == 2
        assert (await OcrJob.get(id=old.id)).photos is None
        assert [p["key"] for p in (await OcrJob.get(id=fresh.id)).photos] == [p["key"] for p in fresh.photos]
        assert not any((self.tmp / p["key"]).exists() for p in old.photos)
        assert all((self.tmp / p["key"]).exists() for p in fresh.photos)
        assert await photos.purge_expired() == 0  # 다시 돌려도 더 지울 것이 없음

    async def test_purge_respects_retention_setting_and_does_nothing_when_off(self):
        job = await self.job_with_photos(self.user, 2)
        with patch.object(config, "PHOTO_RETENTION_HOURS", 1):
            assert await photos.purge_expired() == 2
        assert (await OcrJob.get(id=job.id)).photos is None
        job2 = await self.job_with_photos(self.user, 100)
        with patch.object(config, "PHOTO_STORAGE", ""):
            assert await photos.purge_expired() == 0
        assert (await OcrJob.get(id=job2.id)).photos is not None

    async def test_if_location_cannot_be_recorded_the_uploaded_photos_are_removed(self):
        user = await User.create(login_id="ph-rec@example.com", password_hash="x", birth_year=1950, sex=Sex.F)
        job = await OcrJob.create(user=user, file_count=1)
        saved = await photos.upload_job_photos(job.id, user.id, [Blob(1, b"A", "jpg", "a.jpg")])
        assert (self.tmp / saved[0]["key"]).exists()
        with patch.object(OcrJob, "filter", side_effect=RuntimeError("db down")), self.assertRaises(RuntimeError):
            await photos.record_job_photos(job.id, saved)
        assert not (self.tmp / saved[0]["key"]).exists()  # 위치를 모르는 사진은 남기지 않음

    async def test_failed_delete_keeps_the_key_for_next_time(self):
        job = await self.job_with_photos(self.user, 30)
        real_delete = photo_store.delete

        async def flaky(key):
            if key.endswith("/1.jpg"):
                raise photo_store.PhotoStoreError("boom")
            await real_delete(key)

        with patch.object(photo_store, "delete", flaky):
            assert await photos.purge_expired() == 1  # 2번 사진만 지움
        left = (await OcrJob.get(id=job.id)).photos
        assert [p["fileIndex"] for p in left] == [1]
        assert await photos.purge_expired() == 1  # 다음에 다시 지움
        assert (await OcrJob.get(id=job.id)).photos is None

    async def test_delete_user_photos_removes_everything_of_that_user_at_once(self):
        mine = await self.job_with_photos(self.user, 0)
        mine_old = await self.job_with_photos(self.user, 30)
        theirs = await self.job_with_photos(self.other, 0)
        assert await photos.delete_user_photos(self.user.id) == 4
        assert (await OcrJob.get(id=mine.id)).photos is None and (await OcrJob.get(id=mine_old.id)).photos is None
        assert (await OcrJob.get(id=theirs.id)).photos is not None  # 다른 사용자 것은 그대로
        assert all((self.tmp / p["key"]).exists() for p in theirs.photos)


class TestUploadStoresPhotos(OcrApiCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        patcher = patch.object(config, "PHOTO_DISK_DIR", str(self.tmp))
        patcher.start()
        self.addCleanup(patcher.stop)

    async def post(self, client, headers, photo: bytes):
        sample = json.loads(clova.SAMPLE.read_text(encoding="utf-8"))

        async def fake(content, fmt, name):
            return sample

        with patch.object(clova, "recognize", fake):
            return await client.post(
                "/api/v1/prescriptions", files=[("files", ("p.jpg", photo, "image/jpeg"))], headers=headers
            )

    async def test_upload_saves_photo_and_key_when_storage_is_on(self):
        photo = jpeg_of_size(1200, 1600)
        async with self.client() as client:
            headers = await self.auth(client, "ph-on@example.com")
            with patch.object(config, "PHOTO_STORAGE", "disk"):
                res = await self.post(client, headers, photo)
        assert res.status_code == status.HTTP_202_ACCEPTED
        job = await OcrJob.get(id=res.json()["jobId"])
        assert job.photos is not None and len(job.photos) == 1 and job.photos[0]["fileIndex"] == 1
        assert (self.tmp / job.photos[0]["key"]).read_bytes() == photo

    async def test_upload_does_not_store_when_storage_is_off(self):
        async with self.client() as client:
            headers = await self.auth(client, "ph-off@example.com")
            res = await self.post(client, headers, jpeg_of_size(1200, 1600))
        assert (await OcrJob.get(id=res.json()["jobId"])).photos is None
        assert list(self.tmp.iterdir()) == []

    async def test_storage_failure_does_not_stop_reading(self):
        async def broken(key, content):
            raise photo_store.PhotoStoreError("boom")

        async with self.client() as client:
            headers = await self.auth(client, "ph-fail@example.com")
            with patch.object(config, "PHOTO_STORAGE", "disk"), patch.object(photo_store, "put", broken):
                res = await self.post(client, headers, jpeg_of_size(1200, 1600))
            job = (await client.get(f"/api/v1/ocr-jobs/{res.json()['jobId']}", headers=headers)).json()
        assert res.status_code == status.HTTP_202_ACCEPTED
        assert job["status"] == "done" and len(job["prescriptionIds"]) == 1
        assert (await OcrJob.get(id=res.json()["jobId"])).photos is None

    async def test_ocr_does_not_wait_for_slow_storage(self):
        """저장소(S3)가 느려도 OCR 결과가 먼저 나온다 — 응답도 OCR도 저장을 기다리지 않음"""
        gate = asyncio.Event()

        async def slow_put(key, content):
            await gate.wait()

        user = await User.create(login_id="ph-slow@example.com", password_hash="x", birth_year=1950, sex=Sex.F)
        await UserConsent.create(user=user, consent_type=ConsentType.SENSITIVE_HEALTH, agreed=True)
        blobs = svc.validate_uploads([("p.jpg", jpeg_of_size(1200, 1600))])
        job = await svc.create_job(user, blobs)
        sample = json.loads(clova.SAMPLE.read_text(encoding="utf-8"))
        ocr_done = asyncio.Event()
        real_run_job = svc.run_job

        async def run_job_then_signal(*args):
            await real_run_job(*args)
            ocr_done.set()

        with (
            patch.object(config, "PHOTO_STORAGE", "disk"),
            patch.object(photo_store, "put", slow_put),
            patch.object(svc, "run_job", run_job_then_signal),
            patch.object(clova, "recognize", AsyncMock(return_value=sample)),
        ):
            task = asyncio.create_task(svc.process_job(job.id, user.id, blobs))
            await asyncio.wait_for(ocr_done.wait(), timeout=20)  # 저장이 막혀 있어도 OCR은 끝남
            assert not task.done()  # 저장은 아직 기다리는 중
            assert (await OcrJob.get(id=job.id)).status.value == "done"
            assert (await OcrJob.get(id=job.id)).photos is None
            gate.set()
            await task
        assert (await OcrJob.get(id=job.id)).photos is not None  # 저장이 끝난 뒤에 위치를 적음
        assert blobs[0].content == b""  # OCR이 끝나면 메모리 사진은 비움 (저장에는 복사본이 쓰임)

    async def test_stored_bytes_are_the_original_even_though_memory_copy_is_cleared(self):
        user = await User.create(login_id="ph-copy@example.com", password_hash="x", birth_year=1950, sex=Sex.F)
        await UserConsent.create(user=user, consent_type=ConsentType.SENSITIVE_HEALTH, agreed=True)
        photo = jpeg_of_size(1200, 1600)
        blobs = svc.validate_uploads([("p.jpg", photo)])
        job = await svc.create_job(user, blobs)
        sample = json.loads(clova.SAMPLE.read_text(encoding="utf-8"))
        with (
            patch.object(config, "PHOTO_STORAGE", "disk"),
            patch.object(clova, "recognize", AsyncMock(return_value=sample)),
        ):
            await svc.process_job(job.id, user.id, blobs)
        stored = (await OcrJob.get(id=job.id)).photos
        assert (self.tmp / stored[0]["key"]).read_bytes() == photo


class TestS3WithRealBoto3(TestCase):
    """진짜 boto3로 S3 호출 경로를 시험한다 (moto = 가짜 S3 서버). 인자 이름 · 서명 · 오류 처리를 실제 라이브러리가 검사한다.
    진짜 AWS(권한 · 네트워크)는 이 시험으로 알 수 없고 서버에서 따로 확인한다"""

    BUCKET = "ah06-test-photos"
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

    async def test_put_get_delete_with_content_type(self):
        await photo_store.put(KEY, b"abc")
        head = self.s3.head_object(Bucket=self.BUCKET, Key=KEY)
        assert head["ContentType"] == "image/jpeg" and head["ContentLength"] == 3
        assert await photo_store.get(KEY) == b"abc"
        await photo_store.delete(KEY)
        assert "Contents" not in self.s3.list_objects_v2(Bucket=self.BUCKET)
        await photo_store.delete(KEY)  # 없는 키를 또 지워도 오류가 아님

    async def test_missing_object_and_missing_bucket_become_store_errors(self):
        with self.assertRaises(photo_store.PhotoStoreError) as cm:
            await photo_store.get("ocr/1/1/1.jpg")
        assert str(cm.exception) == "NoSuchKey"
        with (
            patch.object(config, "PHOTO_S3_BUCKET", "no-such-bucket-xyz"),
            self.assertRaises(photo_store.PhotoStoreError) as cm,
        ):
            await photo_store.put(KEY, b"x")
        assert str(cm.exception) == "NoSuchBucket"

    async def test_client_has_timeouts_and_region_and_no_hardcoded_keys(self):
        client = photo_store._s3_client()
        assert client.meta.region_name == self.REGION
        assert (client.meta.config.connect_timeout, client.meta.config.read_timeout) == (5, 15)
        assert client.meta.config.retries == {"mode": "standard", "total_max_attempts": 3}  # 처음 + 다시 시도 2번
        assert photo_store._s3_client() is client  # 한 번만 만들어 재사용

    async def test_whole_lifecycle_on_s3_save_then_purge_after_24_hours(self):
        user = await User.create(login_id="ph-s3@example.com", password_hash="x", birth_year=1950, sex=Sex.F)
        blobs = [Blob(1, b"A" * 10, "jpg", "a.jpg"), Blob(2, b"%PDF-1.4", "pdf", "b.pdf")]
        job = await OcrJob.create(user=user, file_count=2)
        assert await photos.save_job_photos(job.id, user.id, blobs) == 2
        keys = sorted(o["Key"] for o in self.s3.list_objects_v2(Bucket=self.BUCKET)["Contents"])
        assert keys == [f"ocr/{user.id}/{job.id}/1.jpg", f"ocr/{user.id}/{job.id}/2.pdf"]
        assert await photos.purge_expired() == 0  # 24시간 전에는 그대로
        later = datetime.now(UTC) + timedelta(hours=25)
        assert await photos.purge_expired(now=later) == 2
        assert "Contents" not in self.s3.list_objects_v2(Bucket=self.BUCKET)
        assert (await OcrJob.get(id=job.id)).photos is None

    async def test_permission_error_from_s3_keeps_keys_for_retry(self):
        user = await User.create(login_id="ph-denied@example.com", password_hash="x", birth_year=1950, sex=Sex.F)
        job = await OcrJob.create(user=user, file_count=1)
        await photos.save_job_photos(job.id, user.id, [Blob(1, b"A", "jpg", "a.jpg")])

        def denied(*a, **kw):
            raise ClientError({"Error": {"Code": "AccessDenied", "Message": "x"}}, "DeleteObject")

        with patch.object(photo_store._s3_client(), "delete_object", denied):
            assert await photos.purge_expired(now=datetime.now(UTC) + timedelta(hours=25)) == 0
        assert (await OcrJob.get(id=job.id)).photos is not None  # 못 지웠으니 위치를 남겨 다음에 다시 지움
        assert await photos.purge_expired(now=datetime.now(UTC) + timedelta(hours=25)) == 1
