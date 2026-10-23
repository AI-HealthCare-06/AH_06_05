"""정기 작업 — 보관 시간이 지난 처방전 사진 지우기 (10/22 결정 1: 24시간)"""

import logging
from typing import Any

from app.services.ocr import photos

logger = logging.getLogger(__name__)


async def purge_photos(ctx: dict[str, Any]) -> int:
    deleted = await photos.purge_expired()
    if deleted:
        logger.info("보관 시간이 지난 사진 %s장을 지움", deleted)
    return deleted
