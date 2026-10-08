"""약제급여목록 · 상병마스터를 DB에 넣기

    uv run --with openpyxl python scripts/data/load_masters.py

원본: data/raw/hira/ (깃허브에 안 올림, 출처는 docs/data/SOURCES.md). 여러 번 돌려도 됨 (있으면 고쳐 씀)
"""

import argparse
import asyncio
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tortoise import Tortoise  # noqa: E402

from app.core.db.databases import TORTOISE_ORM  # noqa: E402
from app.models.masters import Disease, DrugProduct  # noqa: E402
from app.services.master_loader import read_diseases, read_drug_list, upsert  # noqa: E402

RAW = ROOT / "data" / "raw" / "hira"
DRUGS = RAW / "약제급여목록및급여상한금액표_(2026.9.1.)_공개용(비인가자) 1부.xlsx"
DISEASES = RAW / "건강보험심사평가원_상병마스터_20250930.csv"


async def main(drugs: Path, diseases: Path) -> None:
    await Tortoise.init(config=TORTOISE_ORM)
    try:
        t = time.perf_counter()
        n = await upsert(DrugProduct, read_drug_list(drugs), "edi_code")
        print(f"drug_products {n:,}건 ({time.perf_counter() - t:.1f}초)")
        t = time.perf_counter()
        n = await upsert(Disease, read_diseases(diseases), "code")
        print(f"diseases {n:,}건 ({time.perf_counter() - t:.1f}초)")
    finally:
        await Tortoise.close_connections()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--drugs", type=Path, default=DRUGS)
    p.add_argument("--diseases", type=Path, default=DISEASES)
    a = p.parse_args()
    asyncio.run(main(a.drugs, a.diseases))
