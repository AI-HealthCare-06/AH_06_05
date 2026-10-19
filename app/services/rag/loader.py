"""evidence_chunks 적재. 시험 폴더에서 내보낸 조각 파일(JSON 한 줄에 조각 하나)을 읽어 넣는다.

- 조각 파일에 벡터가 있으면 그대로 넣는다 (OpenAI를 부르지 않음). 시험 폴더 `export_evidence_chunks.py`가 이미 계산된
  임베딩(text-embedding-3-small)을 함께 내보낸다.
- 벡터가 없는 조각, 또는 `reembed=True`이면 `embed_text`를 OpenAI로 임베딩해 채운다 (키 필요, 96개씩).
- 같은 chunk_id는 덮어쓴다. 여러 번 실행해도 같다.
"""

import json
from pathlib import Path
from typing import Any

from app.core import config
from app.models.rag import EMBEDDING_DIM, ChunkKind, EvidenceChunk
from app.services.rag.llm import LLM, OpenAIClient

BATCH = 96
FILE_MODEL = "text-embedding-3-small"  # 조각 파일의 벡터를 만든 모델 (시험 폴더 cache/emb_small.json)


def read_rows(path: Path) -> list[dict[str, Any]]:
    rows = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
        if line.strip():
            row = json.loads(line)
            row.setdefault("source_order", n)
            rows.append(row)
    return rows


def _to_model(row: dict[str, Any]) -> EvidenceChunk:
    kind = ChunkKind(row["kind"])
    vector = row.get("embedding")
    if vector is not None and len(vector) != EMBEDDING_DIM:
        raise ValueError(f"{row['id']}: 벡터가 {len(vector)}차원입니다 ({EMBEDDING_DIM}차원이어야 함)")
    ctx = row.get("ctx") or ""
    return EvidenceChunk(
        chunk_id=row["id"],
        kind=kind,
        drug_code=row.get("drug"),
        disease_code=row.get("disease"),
        section=row.get("letter"),
        group_key=row["group"],
        seq=row["order"],
        source_order=row["source_order"],
        heading=ctx,
        content=row["raw"],
        search_text=f"{ctx} {row['raw']}".strip(),
        embed_text=row["embed_text"],
        drug_name=row.get("drug_name"),
        source_ids=row.get("members") or [row["id"]],
        embedding=vector,
        embedding_model=row.get("embedding_model") or (FILE_MODEL if vector is not None else None),
    )


async def fill_embeddings(rows: list[dict[str, Any]], llm: LLM, reembed: bool = False) -> int:
    """벡터가 없는 조각(reembed면 전부)에 OpenAI 임베딩을 채운다. 만든 개수를 돌려줌"""
    todo = [r for r in rows if reembed or r.get("embedding") is None]
    for i in range(0, len(todo), BATCH):
        part = todo[i : i + BATCH]
        for row, vec in zip(part, await llm.embed([r["embed_text"] for r in part]), strict=True):
            row["embedding"] = vec
            row["embedding_model"] = config.OPENAI_EMBEDDING_MODEL
    return len(todo)


async def load_rows(rows: list[dict[str, Any]], *, llm: LLM | None = None, reembed: bool = False) -> dict[str, int]:
    """조각을 저장한다. 돌려주는 값: {"loaded": 넣은 수, "embedded": OpenAI로 새로 만든 벡터 수}"""
    embedded = 0
    if reembed or any(r.get("embedding") is None for r in rows):
        embedded = await fill_embeddings(rows, llm or OpenAIClient(), reembed)
    models = [_to_model(r) for r in rows]
    for i in range(0, len(models), 200):
        await EvidenceChunk.bulk_create(
            models[i : i + 200],
            on_conflict=["chunk_id"],
            update_fields=[
                "kind", "drug_code", "disease_code", "section", "group_key", "seq", "source_order", "heading", "content",
                "search_text", "embed_text", "drug_name", "source_ids", "embedding", "embedding_model",
            ],
        )  # fmt: skip
    return {"loaded": len(models), "embedded": embedded}
