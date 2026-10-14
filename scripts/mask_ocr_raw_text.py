"""이미 저장된 OCR 원문(prescriptions.ocr_raw_text)에도 마스킹 적용 (실행: python scripts/mask_ocr_raw_text.py [--apply])

10/14 이전에 저장된 원문은 가려지지 않았다. 기본은 몇 건이 바뀌는지만 보여 주고(--apply 없이), --apply를 주면 저장한다.
이미 가려진 글자에는 영향이 없어 여러 번 실행해도 같다.
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tortoise import Tortoise  # noqa: E402

from app.core.db.databases import TORTOISE_APP_MODELS, TORTOISE_ORM  # noqa: E402
from app.models.ocr import Prescription  # noqa: E402
from app.services.ocr.mask import mask  # noqa: E402


async def run(apply: bool) -> None:
    changed = total = 0
    async for rx in Prescription.filter(ocr_raw_text__not_isnull=True).only("id", "ocr_raw_text"):
        total += 1
        masked = mask(rx.ocr_raw_text or "")
        if masked != rx.ocr_raw_text:
            changed += 1
            if apply:
                await Prescription.filter(id=rx.id).update(ocr_raw_text=masked)
    print(f"원문 {total}건 중 {changed}건을 {'가렸어요' if apply else '가릴 수 있어요 (저장하려면 --apply)'}")


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
