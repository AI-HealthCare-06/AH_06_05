"""근거 검색용 조각 표 (ERD v1.5 evidence_chunks) — 챗봇이 읽는 약 허가문서 문장과 생활습관 팩트표 조각

시험 폴더(rag_sandbox/embed_threshold)에서 정리한 "정리 조각 v2" 1,044개와 같은 모양이다. 벡터는 pgvector(vector(1536))에 두고,
글자 조각 점수는 pg_trgm word_similarity로 같은 표에서 계산한다 (약 코드나 질환 코드로 먼저 좁힌 뒤 그 안에서만 비교).
"""

from enum import StrEnum
from typing import Any

from tortoise import fields, models
from tortoise.fields.base import Field

EMBEDDING_DIM = 1536


class VectorField(Field[str]):
    """pgvector vector(1536). 값은 "[0.1,0.2,...]" 글자로 주고받는다 (asyncpg가 글자 모양으로 보내 줌)"""

    SQL_TYPE = f"vector({EMBEDDING_DIM})"

    def to_db_value(self, value: Any, instance: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            return value
        return "[" + ",".join(f"{x:.7g}" for x in value) + "]"

    def to_python_value(self, value: Any) -> Any:
        return value


class ChunkKind(StrEnum):
    DRUG = "drug"  # 약 허가문서 문장 (효능효과 E, 주의사항 S, 용법용량 P)
    FACT = "fact"  # 생활습관 팩트표 조각 (질환별)
    CROSS = "cross"  # 질환이 겹칠 때의 규칙


class EvidenceChunk(models.Model):
    id = fields.BigIntField(primary_key=True)
    chunk_id = fields.CharField(
        max_length=150,
        unique=True,
        description="출처 번호 (예: D:641900040:S12, F:HTN:life:나트륨 줄이기). 챗봇이 돌려받는 sentenceId",
    )
    kind = fields.CharEnumField(enum_type=ChunkKind, max_length=10)
    drug_code = fields.CharField(max_length=9, null=True, db_index=True, description="급여 EDI 제품코드 (drug 조각)")
    disease_code = fields.CharField(
        max_length=10, null=True, db_index=True, description="팩트표 질환 id (fact 조각, 예: HTN)"
    )
    section = fields.CharField(max_length=1, null=True, description="E 효능효과 / S 주의사항 / P 용법용량 (drug 조각)")
    group_key = fields.CharField(
        max_length=200, db_index=True, description="같은 소항목 묶음 키 (후보를 고른 뒤 같은 소항목 문장을 같이 보냄)"
    )
    seq = fields.IntField(description="같은 약, 같은 구분 안에서의 순서")
    source_order = fields.IntField(description="시험에서 쓴 조각 순서 (후보 목록 순서를 같게 하려고 보존)")
    heading = fields.CharField(max_length=300, default="", description="큰제목 > 소항목 경로")
    content = fields.TextField(description="근거 글 원문")
    search_text = fields.TextField(description="글자 조각 검색용 (heading + content)")
    embed_text = fields.TextField(description="임베딩에 넣은 글 (약 이름 + 구분 + 경로 + 본문)")
    drug_name = fields.CharField(max_length=300, null=True, description="질문 프롬프트와 근거 머리말에 쓰는 약 이름")
    source_ids: Any = fields.JSONField(
        default=list, description="이 조각이 합친 허가정보 문장 번호들 (표를 한 조각으로 푼 경우 여러 개)"
    )
    embedding = VectorField(null=True, description="text-embedding-3-small 1536차원")
    embedding_model = fields.CharField(
        max_length=50, null=True, description="벡터를 만든 모델 (바꾸면 새로 만들어야 함)"
    )
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "evidence_chunks"
