"""진짜 OpenAI로 근거 검색을 돌려 봄 (실행: uv run python scripts/rag/smoke_openai.py)

먼저 마이그레이션과 조각 넣기를 마치고 .env에 OPENAI_API_KEY가 있어야 한다. 키 값은 출력하지 않는다.
옵션 없이 실행하면 DB에 있는 약 코드 2개와 질환 코드 1개로 정해 둔 질문 5개를 보낸다.
질문 하나만 보려면 --question 과 --drug (여러 번 가능), 필요하면 --disease 를 준다.
질문마다 통과 여부, 근거 번호와 글, 재작성한 질문, 판정 3개, 단계별 시간을 출력한다.
OpenAI 호출이 하나라도 실패하면(reason=llm_error) 종료 코드 1, 키나 조각이 비어 있으면 2.
한 질문에 채팅 호출 5번(재작성 1, 고르기 1, 판정 3)과 임베딩 호출 1번(질문 2개를 한 번에)이 든다.
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tortoise import Tortoise  # noqa: E402

from app.core import config  # noqa: E402
from app.core.db.databases import TORTOISE_APP_MODELS, TORTOISE_ORM  # noqa: E402
from app.models.rag import EvidenceChunk  # noqa: E402
from app.services.rag import search  # noqa: E402

TEXT_SHOW = 120  # 근거 글을 화면에 보일 최대 글자 수


async def run_one(question: str, drugs: list[str], diseases: list[str]) -> bool:
    """질문 하나를 돌려 결과를 출력한다. OpenAI 호출이 실패했으면 False"""
    r = await search(question, drugs, diseases)
    print("-" * 60)
    print(f"질문: {question}  (약 {drugs}, 질환 {diseases})")
    if r.evidence:
        print(f"결과: 통과 (근거 {len(r.evidence)}개)")
    else:
        print(f"결과: 막힘 (reason={r.reason})")
    print(f"재작성: {r.rewritten}")
    if r.verdicts:
        v = r.verdicts
        print(f"판정: A={v.a} B={v.b}(직접 {v.b_direct}) C={v.c}")
    print(f"단계별 시간(초): {r.seconds}")
    for e in r.evidence:
        print(f"  {e.sentence_id}  {e.heading}  {e.text[:TEXT_SHOW].replace(chr(10), ' ')}")
    return r.reason != "llm_error"


async def main(question: str | None, drugs: list[str], diseases: list[str]) -> int:
    if not config.OPENAI_API_KEY:
        print("OPENAI_API_KEY가 비어 있습니다. .env에 넣고 다시 실행하세요.")
        return 2
    print(
        f"키 있음 (길이 {len(config.OPENAI_API_KEY)}), 채팅 모델 {config.OPENAI_CHAT_MODEL}, 임베딩 모델 {config.OPENAI_EMBEDDING_MODEL}"
    )
    await Tortoise.init(config=TORTOISE_ORM)
    Tortoise.init_models(TORTOISE_APP_MODELS, "models")
    try:
        rows = await EvidenceChunk.all()
        print(f"조각 {len(rows)}개")
        if not rows:
            print("조각이 비어 있습니다. aerich upgrade 후 load_evidence_chunks.py를 먼저 실행하세요.")
            return 2
        if question:
            cases = [(question, drugs, diseases)]
        else:
            known_drugs = sorted({r.drug_code for r in rows if r.drug_code})[:2]
            known_diseases = sorted({r.disease_code for r in rows if r.disease_code})[:1]
            print(f"약 코드 {known_drugs}, 질환 코드 {known_diseases}")
            if not known_drugs:
                print("약 코드가 있는 조각이 없습니다.")
                return 2
            cases = [
                ("이 약은 언제 먹어야 해요?", known_drugs[:1], []),
                ("이 약 먹는 동안 술 마셔도 되나요?", known_drugs[:1], known_diseases),
                ("이 두 약을 같이 먹어도 되나요?", known_drugs, []),
                ("자몽 주스랑 같이 먹어도 돼요?", known_drugs[:1], []),
                ("오늘 저녁 메뉴 추천해 주세요", known_drugs[:1], []),
            ]
        failed = 0
        for q, dr, di in cases:
            if not await run_one(q, dr, di):
                failed += 1
        print("=" * 60)
        print(f"OpenAI 호출 실패 {failed}건 / 질문 {len(cases)}개")
        return 1 if failed else 0
    finally:
        await Tortoise.close_connections()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--question", help="이 질문 하나만 보낸다")
    ap.add_argument("--drug", action="append", default=[], help="약 코드 (여러 번 가능, --question과 함께)")
    ap.add_argument("--disease", action="append", default=[], help="질환 코드 (여러 번 가능, --question과 함께)")
    args = ap.parse_args()
    if args.question and not (args.drug or args.disease):
        ap.error("--question에는 --drug 또는 --disease가 하나 이상 필요합니다")
    sys.exit(asyncio.run(main(args.question, args.drug, args.disease)))
