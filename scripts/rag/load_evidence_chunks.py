"""근거 조각(evidence_chunks)을 DB에 넣음 (실행: uv run python scripts/rag/load_evidence_chunks.py <조각 파일.jsonl> [--reembed])

조각 파일은 시험 폴더(rag_sandbox/embed_threshold)에서 `python3 export_evidence_chunks.py`로 만든
pools/evidence_chunks_v2.jsonl (데모 약 17개의 허가문서 문장과 팩트표 조각 1,044개, 벡터 포함)이다.
벡터가 들어 있으면 OpenAI를 부르지 않는다. 벡터가 없는 조각이 있거나 --reembed를 주면 OPENAI_API_KEY로 임베딩을 만든다.
먼저 마이그레이션을 적용해 두어야 한다 (docker compose exec fastapi uv run --no-sync aerich upgrade).
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tortoise import Tortoise  # noqa: E402

from app.core.db.databases import TORTOISE_APP_MODELS, TORTOISE_ORM  # noqa: E402
from app.models.rag import EvidenceChunk  # noqa: E402
from app.services.rag import loader  # noqa: E402


async def main(path: Path, reembed: bool) -> None:
    await Tortoise.init(config=TORTOISE_ORM)
    Tortoise.init_models(TORTOISE_APP_MODELS, "models")
    try:
        result = await loader.load_rows(loader.read_rows(path), reembed=reembed)
        total = await EvidenceChunk.all().count()
        print(f"넣은 조각 {result['loaded']}개 (OpenAI로 새로 만든 벡터 {result['embedded']}개), 표 전체 {total}개")
    finally:
        await Tortoise.close_connections()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("chunks", type=Path, help="조각 파일 (.jsonl)")
    ap.add_argument("--reembed", action="store_true", help="벡터가 있어도 OpenAI로 다시 만든다")
    args = ap.parse_args()
    asyncio.run(main(args.chunks, args.reembed))
