"""처방전 사진 임시 저장소 (10/22 결정 1, 2)

사진을 올린 시점부터 PHOTO_RETENTION_HOURS(24시간)가 지나면 지운다 (지우기는 photos.purge_expired).
저장하고 읽는 곳을 이 파일 한 곳에 모아 S3와 서버 디스크를 모두 지원하고, 설정값 PHOTO_STORAGE로 고른다.

- "" (기본): 저장하지 않는다 (사진은 메모리에만 두고 처리 뒤 버린다. 안내문 "저장하지 않아요"와 같은 동작)
- "s3": S3 버킷. 서버(EC2)에 붙인 역할(IAM)로 접근하므로 접근 키를 설정하지 않는다
- "disk": 서버 디스크의 폴더 (로컬 개발 · 테스트 · S3를 못 쓸 때의 대비)

DB에는 사진이 아니라 파일 위치(키)만 둔다 (ocr_jobs.photos). 키 모양: ocr/<사용자>/<작업>/<사진 번호>.<형식>
"""

import asyncio
import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.core import config

logger = logging.getLogger(__name__)

_KEY = re.compile(r"^ocr/\d+/\d+/\d+\.(jpg|png|pdf)$")  # 이 모양이 아닌 키는 만지지 않는다 (경로 탈출 방지)
_CONTENT_TYPE = {"jpg": "image/jpeg", "png": "image/png", "pdf": "application/pdf"}


class PhotoStoreError(Exception):
    """저장소 호출 실패 (설정 · 네트워크 · 권한)"""


def _mode() -> str:
    """설정값을 소문자 · 앞뒤 공백 없이 읽는다 ("S3 "처럼 적어도 켜지게). 모르는 값은 꺼짐으로 보고 경고한다
    (켜려다 오타로 조용히 꺼져 있지 않게)"""
    mode = config.PHOTO_STORAGE.strip().lower()
    if mode not in ("", "disk", "s3"):
        logger.warning("PHOTO_STORAGE 값을 알 수 없어 사진을 저장하지 않습니다 (disk 또는 s3)")
        return ""
    return mode


def enabled() -> bool:
    return _mode() != ""


def make_key(user_id: int, job_id: int, file_index: int, fmt: str) -> str:
    return f"ocr/{user_id}/{job_id}/{file_index}.{fmt}"


def _check_key(key: str) -> None:
    if not _KEY.match(key):
        raise PhotoStoreError("사진 키 모양이 올바르지 않습니다")


# ── 서버 디스크 ───────────────────────────────────────────────────────────────────────────────
def _disk_path(key: str) -> Path:
    return Path(config.PHOTO_DISK_DIR) / key


def _disk_put(key: str, content: bytes) -> None:
    path = _disk_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def _disk_get(key: str) -> bytes:
    return _disk_path(key).read_bytes()


def _disk_delete(key: str) -> None:
    path = _disk_path(key)
    path.unlink(missing_ok=True)
    for parent in (path.parent, path.parent.parent):  # 비어 있는 작업 · 사용자 폴더 정리
        try:
            parent.rmdir()
        except OSError:
            break


# ── S3 ───────────────────────────────────────────────────────────────────────────────────────
@lru_cache(maxsize=1)
def _s3_client() -> Any:
    import boto3
    from botocore.config import Config as BotoConfig

    return boto3.client(
        "s3",
        region_name=config.PHOTO_S3_REGION,
        config=BotoConfig(connect_timeout=5, read_timeout=15, retries={"max_attempts": 2, "mode": "standard"}),
    )


def _bucket() -> str:
    if not config.PHOTO_S3_BUCKET:
        raise PhotoStoreError("PHOTO_S3_BUCKET이 비어 있습니다")
    return config.PHOTO_S3_BUCKET


def _s3_put(key: str, content: bytes) -> None:
    _s3_client().put_object(Bucket=_bucket(), Key=key, Body=content, ContentType=_CONTENT_TYPE[key.rsplit(".", 1)[1]])


def _s3_get(key: str) -> bytes:
    return _s3_client().get_object(Bucket=_bucket(), Key=key)["Body"].read()


def _s3_delete(key: str) -> None:
    _s3_client().delete_object(Bucket=_bucket(), Key=key)  # 없는 키를 지워도 오류가 아니다


# ── 바깥에서 쓰는 함수 (동기 호출은 별도 스레드에서) ───────────────────────────────────────────────
async def _run(disk: Any, s3: Any, key: str, *args: Any) -> Any:
    _check_key(key)
    mode = _mode()
    if mode == "disk":
        fn = disk
    elif mode == "s3":
        fn = s3
    else:
        raise PhotoStoreError("사진 저장소가 꺼져 있습니다 (PHOTO_STORAGE)")
    try:
        return await asyncio.to_thread(fn, key, *args)
    except PhotoStoreError:
        raise
    except Exception as e:  # botocore · OSError 등 — 키 · 주소가 로그에 남지 않도록 예외 종류만 적는다
        raise PhotoStoreError(type(e).__name__) from e


async def put(key: str, content: bytes) -> None:
    await _run(_disk_put, _s3_put, key, content)


async def get(key: str) -> bytes:
    return await _run(_disk_get, _s3_get, key)


async def delete(key: str) -> None:
    await _run(_disk_delete, _s3_delete, key)
