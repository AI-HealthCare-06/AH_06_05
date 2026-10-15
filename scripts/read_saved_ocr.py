"""저장해 둔 CLOVA 결과(JSON)를 지금 코드로 다시 읽어 본다 (실행: python scripts/read_saved_ocr.py result_p1.json [...])

CLOVA를 부르지 않고(요금 없음), DB에 아무것도 저장하지 않는다. 읽기(처방전 / 약봉투), 약 이름 · 숫자, 약 마스터와 맞춘 결과를 보여 준다.
약 마스터(drug_products)는 DB에서 읽으므로 DB가 켜져 있어야 한다 (집에서는 DB_HOST=localhost).
화면에는 읽은 약 이름 · 숫자 · 날짜와 약 카드의 복약 안내(가려서)만 찍고 인식 원문은 찍지 않는다.
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tortoise import Tortoise  # noqa: E402

from app.core.db.databases import TORTOISE_APP_MODELS, TORTOISE_ORM  # noqa: E402
from app.services import prescriptions as svc  # noqa: E402
from app.services.ocr.mask import mask  # noqa: E402
from app.services.ocr.pipeline import read  # noqa: E402


async def run(paths: list[str]) -> None:
    matcher, codes = await svc.get_matcher(), await svc.get_codes()
    for p in paths:
        res = read(json.loads(Path(p).read_text(encoding="utf-8")), matcher, codes)
        print(f"\n== {Path(p).name}: {res.status}{'(' + res.reason + ')' if res.reason else ''} · {res.doc_type}")
        if res.status != "ok":
            continue
        print(f"   날짜 {res.issued} · 확인 항목 {res.meta_flags} · 약 줄 수 불일치 {res.row_count_mismatch}")
        for r in res.rows:
            top = r.decision.candidates[0].item_name if r.decision.candidates else "-"
            print(f"   {r.read_name} | {r.dose}/{r.times}/{r.days} | {r.decision.status} | {top} | {r.flags}")
            for g in r.guide:  # 약국이 약 카드에 인쇄한 안내 (저장될 때처럼 가려서 보여 줌)
                print(f"      · {mask(g)}")


async def main(paths: list[str]) -> None:
    await Tortoise.init(config=TORTOISE_ORM)
    Tortoise.init_models(TORTOISE_APP_MODELS, "models")
    try:
        await run(paths)
    finally:
        await Tortoise.close_connections()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    asyncio.run(main(sys.argv[1:]))
