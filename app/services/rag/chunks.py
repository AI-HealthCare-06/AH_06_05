"""근거 조각 읽기: 약 코드와 질환 코드로 범위를 좁히고, 범위 안에서 임베딩(pgvector)과 글자 조각(pg_trgm) 순위를 낸다.

시험 코드(eval2.scope_units, sentence_ranking, evidence_v2.expand, poolgen.show)와 같은 규칙이다.
범위 안의 조각 수는 평균 수백 개라 인덱스 없이 정확한 비교로 충분하다 (docs/design/embedding.md 3장).
"""

from dataclasses import dataclass
from typing import Any

from app.models.rag import EvidenceChunk

SECTION_LABEL = {"E": "효능효과", "S": "주의사항", "P": "용법용량"}
GROUP_CAP = 8  # 소항목 묶음의 최대 조각 수 (소항목 첫 문장은 항상 포함)
SHOW_MAX = 600  # 판정에 보내는 글 한 조각의 최대 글자 수 (넘으면 …)

_COLUMNS = "chunk_id, kind, drug_code, disease_code, section, group_key, seq, heading, content, drug_name, source_order"
# $1 약 코드 목록, $2 질환 코드 목록, $3 질환이 있는지. 약도 질환도 없으면 전체 (앞단 규칙이 먼저 막아서 서비스에서는 쓰이지 않음)
_SCOPE = (
    "(( cardinality($1::text[]) = 0 AND cardinality($2::text[]) = 0 ) OR "
    "(kind = 'drug' AND drug_code = ANY($1::text[])) OR "
    "(kind = 'fact' AND disease_code = ANY($2::text[])) OR "
    "(kind = 'cross' AND $3::boolean))"
)


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    kind: str
    drug_code: str | None
    disease_code: str | None
    section: str | None
    group_key: str
    seq: int
    heading: str
    content: str
    drug_name: str | None
    source_order: int

    @staticmethod
    def of(row: dict[str, Any]) -> "Chunk":
        return Chunk(**{k: row[k] for k in _COLUMNS.replace(" ", "").split(",")})


def show(c: Chunk) -> str:
    """판정과 고르기 프롬프트에 넣는 글 (poolgen.show와 같은 모양)"""
    if c.kind == "drug":
        head = f"{c.drug_name} {SECTION_LABEL[c.section or 'S']}" + (f" > {c.heading}" if c.heading else "")
        text = c.content if len(c.content) <= SHOW_MAX else c.content[:SHOW_MAX] + "…"
        return f"[{head}] {text}"
    return c.content


def _db() -> Any:
    return EvidenceChunk._meta.db


def _args(drugs: list[str], diseases: list[str]) -> list[Any]:
    return [drugs, diseases, bool(diseases)]


async def scope_chunks(drugs: list[str], diseases: list[str]) -> list[Chunk]:
    """범위 안의 조각 전부 (시험에서 쓴 조각 순서)"""
    rows = await _db().execute_query_dict(
        f"SELECT {_COLUMNS} FROM evidence_chunks WHERE {_SCOPE} ORDER BY source_order", _args(drugs, diseases)
    )
    return [Chunk.of(r) for r in rows]


async def rank_by_embedding(drugs: list[str], diseases: list[str], vector: list[float], n: int) -> list[str]:
    """질문 벡터와 코사인 거리가 가까운 순서의 chunk_id (동점이면 시험에서 쓴 조각 순서)"""
    text = "[" + ",".join(f"{x:.7g}" for x in vector) + "]"
    rows = await _db().execute_query_dict(
        f"SELECT chunk_id FROM evidence_chunks WHERE {_SCOPE} AND embedding IS NOT NULL "
        "ORDER BY embedding <=> $4::vector, source_order LIMIT $5",
        [*_args(drugs, diseases), text, n],
    )
    return [r["chunk_id"] for r in rows]


async def rank_by_trgm(drugs: list[str], diseases: list[str], text: str, n: int) -> list[str]:
    """pg_trgm word_similarity(질문, 조각 글)이 큰 순서의 chunk_id (동점이면 시험에서 쓴 조각 순서)"""
    rows = await _db().execute_query_dict(
        f"SELECT chunk_id FROM evidence_chunks WHERE {_SCOPE} "
        "ORDER BY word_similarity($4, search_text) DESC, source_order LIMIT $5",
        [*_args(drugs, diseases), text, n],
    )
    return [r["chunk_id"] for r in rows]


async def by_ids(ids: list[str]) -> dict[str, Chunk]:
    if not ids:
        return {}
    rows = await _db().execute_query_dict(
        f"SELECT {_COLUMNS} FROM evidence_chunks WHERE chunk_id = ANY($1::text[])", [ids]
    )
    return {r["chunk_id"]: Chunk.of(r) for r in rows}


async def groups_of(group_keys: list[str]) -> dict[str, list[Chunk]]:
    """소항목 묶음 키 -> 그 묶음의 조각들(순서대로)"""
    if not group_keys:
        return {}
    rows = await _db().execute_query_dict(
        f"SELECT {_COLUMNS} FROM evidence_chunks WHERE group_key = ANY($1::text[]) ORDER BY group_key, seq, source_order",
        [group_keys],
    )
    out: dict[str, list[Chunk]] = {}
    for r in rows:
        out.setdefault(r["group_key"], []).append(Chunk.of(r))
    return out


def expand_group(c: Chunk, group: list[Chunk], cap: int = GROUP_CAP) -> list[Chunk]:
    """고른 조각 하나를 같은 소항목 묶음으로 넓힌다 (evidence_v2.expand의 group 방식). 약 문장이 아니면 자기 자신만"""
    if c.kind != "drug" or len(group) <= cap:
        return group if c.kind == "drug" else [c]
    pos = next(i for i, x in enumerate(group) if x.chunk_id == c.chunk_id)
    lo = max(0, min(pos - cap // 2, len(group) - cap))
    sel = group[lo : lo + cap]
    if group[0] not in sel:  # 소항목 첫 문장(제목)은 항상 붙인다
        sel = [group[0], *sel[:-1]]
    return sel
