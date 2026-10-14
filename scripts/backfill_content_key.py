"""content_key가 없는 기존 처방전에 열쇠를 채움 (실행: python scripts/backfill_content_key.py [--apply])

10/14 이전에 저장한 처방전은 "같은 처방전을 다시 올렸는지" 비교할 열쇠가 없어서 다시 올려도 찾지 못한다.
저장된 병원 · 교부일 · 약 목록으로 같은 규칙의 열쇠를 계산해 채운다 (기본은 건수만 보여 줌, --apply로 저장).
정보가 모자란 처방전(병원 · 교부일 · 약이 비어 있음)은 채우지 않는다. 여러 번 실행해도 같다.
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tortoise import Tortoise  # noqa: E402

from app.core.db.databases import TORTOISE_APP_MODELS, TORTOISE_ORM  # noqa: E402
from app.models.ocr import Prescription  # noqa: E402
from app.services.prescriptions import saved_content_key  # noqa: E402


async def run(apply: bool) -> None:
    todo = filled = 0
    for rx in await Prescription.filter(content_key__isnull=True).order_by("id"):
        todo += 1
        key = await saved_content_key(rx)
        if key is not None:
            filled += 1
            if apply:
                await Prescription.filter(id=rx.id).update(content_key=key)
    print(
        f"열쇠가 없는 처방전 {todo}건 중 {filled}건에 {'채웠어요' if apply else '채울 수 있어요 (저장하려면 --apply)'}"
    )


async def main(apply: bool) -> None:
    await Tortoise.init(config=TORTOISE_ORM)
    Tortoise.init_models(TORTOISE_APP_MODELS, "models")
    try:
        await run(apply)
    finally:
        await Tortoise.close_connections()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--apply", action="store_true", help="실제로 저장 (없으면 건수만 보여 줌)")
    asyncio.run(main(ap.parse_args().apply))
