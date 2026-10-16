"""이미 저장된 OCR 원문(prescriptions.ocr_raw_text)을 비운다 (실행: python scripts/clear_ocr_raw_text.py [--apply])

10/15부터 인식 원문은 저장하지 않는다 (docs/design/ocr_mask.md). 그 전에 개발 DB에 저장된 원문이 남아 있으면 이 스크립트로 비운다.
기본은 몇 건이 비워지는지만 보여 주고(--apply 없이), --apply를 주면 비운다. 여러 번 실행해도 같다.
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tortoise import Tortoise  # noqa: E402

from app.core.db.databases import TORTOISE_APP_MODELS, TORTOISE_ORM  # noqa: E402
from app.models.ocr import Prescription  # noqa: E402


async def run(apply: bool) -> None:
    total = await Prescription.all().count()
    stored = await Prescription.filter(ocr_raw_text__not_isnull=True).count()
    if apply and stored:
        await Prescription.filter(ocr_raw_text__not_isnull=True).update(ocr_raw_text=None)
    print(
        f"처방전 {total}건 중 원문이 저장된 {stored}건을 {'비웠어요' if apply else '비울 수 있어요 (비우려면 --apply)'}"
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
    ap.add_argument("--apply", action="store_true", help="실제로 비움 (없으면 건수만 보여 줌)")
    asyncio.run(main(ap.parse_args().apply))
