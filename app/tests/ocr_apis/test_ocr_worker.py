"""OCR을 arq 워커로 보내는 흐름 (10/26 이전): 맡기기 · 못 맡길 때의 대비 · 워커가 하는 일 · 다시 시도"""

import asyncio
import importlib.util
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from arq import Retry
from starlette import status
from tortoise.contrib.test import TestCase

from app.core import config
from app.models.ocr import OcrJob, OcrJobStatus, Prescription
from app.models.users import ConsentType, Sex, User, UserConsent
from app.services import prescriptions as svc
from app.services.ocr import clova, photo_store, queue
from app.tests.ocr_apis.test_ocr_apis import OcrApiCase, jpeg_of_size

REPO = Path(__file__).resolve().parents[3]


class WorkerCase(OcrApiCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        for name, value in (("PHOTO_DISK_DIR", str(self.tmp)), ("PHOTO_STORAGE", "disk"), ("OCR_WORKER", True)):
            patcher = patch.object(config, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.sample = json.loads(clova.SAMPLE.read_text(encoding="utf-8"))

    async def new_job(self, login: str = "w1@example.com", photo: bytes | None = None):
        user = await User.create(login_id=login, password_hash="x", birth_year=1950, sex=Sex.F)
        await UserConsent.create(user=user, consent_type=ConsentType.SENSITIVE_HEALTH, agreed=True)
        blobs = svc.validate_uploads([("p.jpg", photo or jpeg_of_size(1200, 1600, login.encode()))])
        job = await svc.create_job(user, blobs)
        return user, job, blobs


class TestHandToWorker(WorkerCase):
    async def test_off_by_default_does_nothing(self):
        user, job, blobs = await self.new_job()
        with patch.object(config, "OCR_WORKER", False), patch.object(queue, "enqueue_ocr", AsyncMock()) as q:
            assert await svc.hand_to_worker(job.id, user.id, blobs) is False
        q.assert_not_awaited()
        assert list(self.tmp.rglob("*.jpg")) == []

    async def test_needs_photo_storage_too(self):
        user, job, blobs = await self.new_job()
        with patch.object(config, "PHOTO_STORAGE", ""), patch.object(queue, "enqueue_ocr", AsyncMock()) as q:
            assert await svc.hand_to_worker(job.id, user.id, blobs) is False
        q.assert_not_awaited()

    async def test_uploads_photos_records_keys_then_enqueues(self):
        user, job, blobs = await self.new_job()
        with patch.object(queue, "enqueue_ocr", AsyncMock(return_value=True)) as q:
            assert await svc.hand_to_worker(job.id, user.id, blobs) is True
        q.assert_awaited_once_with(job.id, user.id)
        saved = (await OcrJob.get(id=job.id)).photos
        assert [p["fileIndex"] for p in saved] == [1] and (self.tmp / saved[0]["key"]).exists()

    async def test_storage_failure_falls_back_without_leaving_photos(self):
        user, job, blobs = await self.new_job()

        async def broken(key, content):
            raise photo_store.PhotoStoreError("boom")

        with patch.object(photo_store, "put", broken), patch.object(queue, "enqueue_ocr", AsyncMock()) as q:
            assert await svc.hand_to_worker(job.id, user.id, blobs) is False
        q.assert_not_awaited()
        assert (await OcrJob.get(id=job.id)).photos is None

    async def test_slow_storage_is_cut_off_and_falls_back(self):
        user, job, blobs = await self.new_job()

        async def slow(key, content):
            await asyncio.sleep(5)

        with (
            patch.object(config, "OCR_UPLOAD_WAIT_SEC", 0.05),
            patch.object(photo_store, "put", slow),
            patch.object(queue, "enqueue_ocr", AsyncMock()) as q,
        ):
            assert await svc.hand_to_worker(job.id, user.id, blobs) is False
        q.assert_not_awaited()

    async def test_queue_failure_falls_back(self):
        user, job, blobs = await self.new_job()
        with patch.object(queue, "enqueue_ocr", AsyncMock(return_value=False)):
            assert await svc.hand_to_worker(job.id, user.id, blobs) is False

    async def test_upload_api_returns_queued_and_leaves_the_work_to_the_worker(self):
        async with self.client() as client:
            headers = await self.auth(client, "w2@example.com")
            with patch.object(queue, "enqueue_ocr", AsyncMock(return_value=True)):
                res = await self.upload(client, headers)
            assert res.status_code == status.HTTP_202_ACCEPTED and res.json()["status"] == "queued"
            job = await OcrJob.get(id=res.json()["jobId"])
            assert job.status == OcrJobStatus.QUEUED and job.photos is not None  # 서버가 직접 읽지 않음
            assert await Prescription.filter(ocr_job_id=job.id).count() == 0

    async def test_upload_api_reads_in_server_when_queue_is_down(self):
        async with self.client() as client:
            headers = await self.auth(client, "w3@example.com")
            with (
                patch.object(queue, "enqueue_ocr", AsyncMock(return_value=False)),
                patch.object(clova, "recognize", AsyncMock(return_value=self.sample)),
            ):
                res = await self.upload(client, headers)
            job = (await client.get(f"/api/v1/ocr-jobs/{res.json()['jobId']}", headers=headers)).json()
        assert job["status"] == "done" and len(job["prescriptionIds"]) == 1


class TestRunQueuedJob(WorkerCase):
    async def stored_job(self, login: str):
        user, job, blobs = await self.new_job(login)
        with patch.object(queue, "enqueue_ocr", AsyncMock(return_value=True)):
            assert await svc.hand_to_worker(job.id, user.id, blobs)
        return user, job

    async def test_worker_reads_photos_from_storage_and_finishes_the_job(self):
        user, job = await self.stored_job("w4@example.com")
        with patch.object(clova, "recognize", AsyncMock(return_value=self.sample)):
            assert await svc.run_queued_job(job.id, user.id, final=False) is False
        job = await OcrJob.get(id=job.id)
        assert job.status == OcrJobStatus.DONE and await Prescription.filter(ocr_job_id=job.id).count() == 1
        assert job.photos is not None  # 사진은 24시간 뒤 따로 지움

    async def test_already_finished_job_is_not_read_again(self):
        user, job = await self.stored_job("w5@example.com")
        with patch.object(clova, "recognize", AsyncMock(return_value=self.sample)) as rec:
            await svc.run_queued_job(job.id, user.id, final=False)
            await svc.run_queued_job(job.id, user.id, final=False)  # 같은 작업이 두 번 전달돼도
        assert rec.await_count == 1

    async def test_other_users_job_is_ignored(self):
        user, job = await self.stored_job("w6@example.com")
        with patch.object(clova, "recognize", AsyncMock(return_value=self.sample)) as rec:
            assert await svc.run_queued_job(job.id, user.id + 999, final=True) is False
        rec.assert_not_awaited()

    async def test_all_clova_failures_ask_for_a_retry_then_fail_on_the_last_try(self):
        user, job = await self.stored_job("w7@example.com")
        boom = AsyncMock(side_effect=clova.ClovaError("down"))
        with patch.object(clova, "recognize", boom):
            assert await svc.run_queued_job(job.id, user.id, final=False) is True
            first = await OcrJob.get(id=job.id)
            assert first.status == OcrJobStatus.QUEUED and first.error_code is None  # 화면에는 계속 읽는 중
            assert await svc.run_queued_job(job.id, user.id, final=True) is False
        last = await OcrJob.get(id=job.id)
        assert last.status == OcrJobStatus.FAILED and last.error_code == "F1"

    async def test_retry_succeeds_when_clova_recovers(self):
        user, job = await self.stored_job("w8@example.com")
        calls = iter([clova.ClovaError("down"), self.sample])

        async def flaky(*a):
            r = next(calls)
            if isinstance(r, Exception):
                raise r
            return r

        with patch.object(clova, "recognize", flaky):
            assert await svc.run_queued_job(job.id, user.id, final=False) is True
            assert await svc.run_queued_job(job.id, user.id, final=False) is False
        assert (await OcrJob.get(id=job.id)).status == OcrJobStatus.DONE

    async def test_partial_success_is_not_retried(self):
        """한 장이라도 읽었으면 다시 읽지 않는다 (이미 저장한 것을 두 번 읽지 않게)"""
        user, job, blobs = await self.new_job("w9@example.com")
        blobs = svc.validate_uploads(
            [("a.jpg", jpeg_of_size(1200, 1600, b"a")), ("b.jpg", jpeg_of_size(1200, 1600, b"b"))]
        )
        with patch.object(queue, "enqueue_ocr", AsyncMock(return_value=True)):
            await svc.hand_to_worker(job.id, user.id, blobs)
        calls = iter([self.sample, clova.ClovaError("down")])

        async def one_ok(*a):
            r = next(calls)
            if isinstance(r, Exception):
                raise r
            return r

        with patch.object(clova, "recognize", one_ok):
            assert await svc.run_queued_job(job.id, user.id, final=False) is False
        done = await OcrJob.get(id=job.id)
        assert done.status == OcrJobStatus.DONE and done.error_code == "F2"

    async def test_missing_photos_retry_once_then_fail(self):
        user, job = await self.stored_job("w10@example.com")
        for p in (await OcrJob.get(id=job.id)).photos:
            (self.tmp / p["key"]).unlink()
        with patch.object(clova, "recognize", AsyncMock()) as rec:
            assert await svc.run_queued_job(job.id, user.id, final=False) is True
            assert await svc.run_queued_job(job.id, user.id, final=True) is False
        rec.assert_not_awaited()
        failed = await OcrJob.get(id=job.id)
        assert failed.status == OcrJobStatus.FAILED and failed.error_code == "OCR_FAILED"

    async def test_job_without_stored_photos_fails_instead_of_hanging(self):
        user, job, _ = await self.new_job("w11@example.com")
        assert await svc.run_queued_job(job.id, user.id, final=True) is False
        assert (await OcrJob.get(id=job.id)).status == OcrJobStatus.FAILED


class TestQueue(TestCase):
    async def test_enqueues_with_fixed_job_id(self):
        pool = SimpleNamespace(enqueue_job=AsyncMock(return_value=object()), exists=AsyncMock(return_value=1))
        with patch.object(queue, "_get_pool", AsyncMock(return_value=pool)):
            assert await queue.enqueue_ocr(7, 3) is True
        pool.enqueue_job.assert_awaited_once_with("ocr_job", 7, 3, _job_id="ocr-7")

    async def test_already_queued_counts_as_handed_over(self):
        pool = SimpleNamespace(enqueue_job=AsyncMock(return_value=None), exists=AsyncMock(return_value=1))
        with patch.object(queue, "_get_pool", AsyncMock(return_value=pool)):
            assert await queue.enqueue_ocr(7, 3) is True

    async def test_dead_worker_means_not_enqueued(self):
        pool = SimpleNamespace(enqueue_job=AsyncMock(), exists=AsyncMock(return_value=0))
        with patch.object(queue, "_get_pool", AsyncMock(return_value=pool)), self.assertLogs(queue.logger, "WARNING"):
            assert await queue.enqueue_ocr(7, 3) is False
        pool.exists.assert_awaited_once_with("arq:queue:health-check")
        pool.enqueue_job.assert_not_awaited()

    async def test_redis_down_returns_false_without_raising(self):
        with (
            patch.object(queue, "_get_pool", AsyncMock(side_effect=ConnectionError("no redis"))),
            self.assertLogs(queue.logger, "WARNING"),
        ):
            assert await queue.enqueue_ocr(7, 3) is False


class TestWorkerEntry(TestCase):
    """ai_worker/ 쪽 얇은 껍데기 (처리 자체는 위 서비스 함수)"""

    @staticmethod
    def load(name: str):
        spec = importlib.util.spec_from_file_location(name, REPO / "ai_worker" / "tasks" / f"{name}.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    async def test_ocr_job_asks_arq_to_retry_with_the_configured_delay(self):
        mod = self.load("ocr_tasks")
        with patch.object(mod.prescriptions, "run_queued_job", AsyncMock(return_value=True)) as run:
            with self.assertRaises(Retry) as cm:
                await mod.ocr_job({"job_try": 1}, 5, 9)
            run.assert_awaited_once_with(5, 9, final=False)
            assert cm.exception.defer_score == config.OCR_WORKER_RETRY_DELAY_SEC * 1000

    async def test_last_try_is_final_and_does_not_retry(self):
        mod = self.load("ocr_tasks")
        with patch.object(mod.prescriptions, "run_queued_job", AsyncMock(return_value=False)) as run:
            await mod.ocr_job({"job_try": config.OCR_WORKER_MAX_TRIES}, 5, 9)
        run.assert_awaited_once_with(5, 9, final=True)

    async def test_purge_task_calls_the_purge(self):
        mod = self.load("maintenance_tasks")
        with patch.object(mod.photos, "purge_expired", AsyncMock(return_value=3)):
            assert await mod.purge_photos({}) == 3
