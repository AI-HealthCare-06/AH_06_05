"""작업 단위로 사진을 저장하고 지운다 (저장소 자체는 photo_store.py)

- upload_job_photos + record_job_photos (= save_job_photos): O-1에서 올린 사진을 저장하고 ocr_jobs.photos에 위치(키)를 적는다
- purge_expired: 올린 지 PHOTO_RETENTION_HOURS가 지난 사진을 지운다 (성공 · 실패 모두, 시간으로만 지움)
- delete_user_photos: 한 사용자의 사진을 모두 바로 지운다 (회원 탈퇴 U-3가 만들어지면 사용자를 지우기 전에 부른다.
  사용자를 먼저 지우면 ocr_jobs 행이 함께 지워져 사진 위치를 잃는다)

지우기는 한 장이 실패해도 나머지를 계속 지우고, 실패한 사진은 위치를 남겨 다음에 다시 지운다.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from app.core import config
from app.models.ocr import OcrJob
from app.services.ocr import photo_store

if TYPE_CHECKING:
    from app.services.prescriptions import Blob

logger = logging.getLogger(__name__)


async def upload_job_photos(job_id: int, user_id: int, blobs: "list[Blob]") -> list[dict[str, Any]]:
    """사진을 저장소에 한꺼번에 올리고 [{"fileIndex", "key"}]를 돌려준다 (DB는 건드리지 않음 — OCR이 DB를 쓰는 동안 같이 돌릴 수 있게).
    하나라도 실패하면 올린 것은 모두 지우고 PhotoStoreError를 올린다"""
    saved = [
        {"fileIndex": b.file_index, "key": photo_store.make_key(user_id, job_id, b.file_index, b.fmt)} for b in blobs
    ]
    results = await asyncio.gather(
        *(photo_store.put(p["key"], b.content) for p, b in zip(saved, blobs, strict=True)), return_exceptions=True
    )
    errors = [r for r in results if isinstance(r, BaseException)]
    if errors:
        await _remove_keys(job_id, saved)  # 없는 키를 지워도 오류가 아님
        first = errors[0]
        raise (
            first
            if isinstance(first, photo_store.PhotoStoreError)
            else photo_store.PhotoStoreError(type(first).__name__)
        )
    return saved


async def _remove_keys(job_id: int, saved: list[dict[str, Any]]) -> None:
    for p in saved:
        try:
            await photo_store.delete(p["key"])
        except photo_store.PhotoStoreError:
            logger.warning("올렸던 사진을 지우지 못함 job=%s (S3 보관 규칙이 하루 안에 지움)", job_id)


async def record_job_photos(job_id: int, saved: list[dict[str, Any]]) -> None:
    """올린 사진의 위치를 ocr_jobs.photos에 적는다. 적지 못하면 올린 사진을 지운다 (위치를 모르는 사진이 남지 않게)"""
    try:
        await OcrJob.filter(id=job_id).update(photos=saved)
    except Exception:
        await _remove_keys(job_id, saved)
        raise


async def save_job_photos(job_id: int, user_id: int, blobs: "list[Blob]") -> int:
    """올리고 적는다. 저장한 수를 돌려준다"""
    saved = await upload_job_photos(job_id, user_id, blobs)
    await record_job_photos(job_id, saved)
    return len(saved)


async def load_job_blobs(job: OcrJob) -> "list[Blob]":
    """워커가 저장소에서 작업의 사진을 읽어 온다. 하나라도 못 읽으면 PhotoStoreError (일부만 읽고 진행하지 않음)"""
    from app.services.prescriptions import Blob

    entries = sorted(job.photos or [], key=lambda p: p["fileIndex"])
    contents = await asyncio.gather(*(photo_store.get(p["key"]) for p in entries))
    return [
        Blob(p["fileIndex"], c, p["key"].rsplit(".", 1)[1], f"photo{p['fileIndex']}")
        for p, c in zip(entries, contents, strict=True)
    ]


async def _delete_job_photos(job: OcrJob) -> int:
    """작업 하나의 사진을 지우고 지운 수를 돌려준다. 못 지운 사진은 위치를 남긴다"""
    left: list[dict[str, Any]] = []
    deleted = 0
    for p in job.photos or []:
        try:
            await photo_store.delete(p["key"])
            deleted += 1
        except photo_store.PhotoStoreError as e:
            logger.warning("사진을 지우지 못함 job=%s (%s)", job.id, e)
            left.append(p)
    await OcrJob.filter(id=job.id).update(photos=left or None)
    return deleted


async def purge_expired(now: datetime | None = None) -> int:
    """보관 시간이 지난 사진을 지운다. 지운 사진 수를 돌려준다"""
    if not photo_store.enabled():
        return 0
    now = now or datetime.now(config.TIMEZONE)
    cutoff = now - timedelta(hours=config.PHOTO_RETENTION_HOURS)
    total = 0
    for job in await OcrJob.filter(created_at__lt=cutoff, photos__not_isnull=True):
        total += await _delete_job_photos(job)
    return total


async def delete_user_photos(user_id: int) -> int:
    """한 사용자의 사진을 모두 지운다 (보관 시간과 상관없이). 지운 사진 수를 돌려준다"""
    if not photo_store.enabled():
        return 0
    total = 0
    for job in await OcrJob.filter(user_id=user_id, photos__not_isnull=True):
        total += await _delete_job_photos(job)
    return total
