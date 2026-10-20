"""약이 둘 이상인 질문에서 근거가 어느 약에서 나오는지 단계마다 센다 (실행: uv run python scripts/rag/two_drug_diag.py --question "..." --drug 코드1 --drug 코드2)

search()와 같은 순서(범위, 재작성, 후보, 고르기, 묶음 넓히기)를 그대로 따라가면서 단계마다 약 코드별 조각 수를 출력한다.
어느 단계에서 한 약으로 쏠리는지 보려는 확인용이고, 서비스 코드는 바꾸지 않는다. 진짜 OpenAI를 질문당 3번(재작성, 임베딩, 고르기) 부른다.
먼저 마이그레이션과 조각 넣기를 마치고 .env에 OPENAI_API_KEY가 있어야 한다. 키 값은 출력하지 않는다.
"""

import argparse
import asyncio
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tortoise import Tortoise  # noqa: E402

from app.core import config  # noqa: E402
from app.core.db.databases import TORTOISE_APP_MODELS, TORTOISE_ORM  # noqa: E402
from app.services.rag import chunks as store  # noqa: E402
from app.services.rag import pipeline as p  # noqa: E402
from app.services.rag.llm import OpenAIClient  # noqa: E402


def count(label: str, items: list[store.Chunk]) -> None:
    c = Counter((x.drug_code or x.kind) for x in items)
    print(f"{label}: 전체 {len(items)}개, 약 코드별 {dict(c)}")


async def main(question: str, drugs: list[str], diseases: list[str]) -> int:
    if not config.OPENAI_API_KEY:
        print("OPENAI_API_KEY가 비어 있습니다. .env에 넣고 다시 실행하세요.")
        return 2
    await Tortoise.init(config=TORTOISE_ORM)
    Tortoise.init_models(TORTOISE_APP_MODELS, "models")
    try:
        llm = OpenAIClient()
        scope = await store.scope_chunks(drugs, diseases)
        count("1 범위", scope)
        if not scope:
            print("범위가 비어 있습니다(약 코드를 확인하세요).")
            return 2
        names = {c.drug_code: c.drug_name for c in scope if c.drug_code and c.drug_name}
        info = p._asker_info(drugs, diseases, names)
        rewritten = await p.rewrite_question(llm, question, [names.get(d, d) for d in drugs], diseases)
        print(f"재작성: {rewritten}")
        vectors = await llm.embed([question, rewritten])
        cands = await p.gather_candidates(scope, drugs, diseases, vectors[0], vectors[1], question, rewritten)
        mode = "범위 전부" if len(scope) <= p.SCOPE_ALL_MAX else f"순위 상위 {p.TOP_N}개씩 4가지"
        count(f"2 후보 ({mode})", cands)
        picked = p.parse_picks(
            await llm.complete(p.selection_prompt(question, rewritten, info, cands)), cands, p.MAX_PICK
        )
        count("3 LLM이 고른 글", picked)
        count("4 소항목 묶음으로 넓힌 근거", await p.expand_picks(picked))
        return 0
    finally:
        await Tortoise.close_connections()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--question", required=True)
    ap.add_argument("--drug", action="append", default=[], help="약 코드 (두 번 이상)")
    ap.add_argument("--disease", action="append", default=[], help="질환 코드")
    args = ap.parse_args()
    if len(args.drug) < 2:
        ap.error("--drug를 두 번 이상 주세요")
    sys.exit(asyncio.run(main(args.question, args.drug, args.disease)))
