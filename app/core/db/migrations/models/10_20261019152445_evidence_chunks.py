from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE TABLE IF NOT EXISTS "evidence_chunks" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "chunk_id" VARCHAR(150) NOT NULL UNIQUE,
    "kind" VARCHAR(10) NOT NULL,
    "drug_code" VARCHAR(9),
    "disease_code" VARCHAR(10),
    "section" VARCHAR(1),
    "group_key" VARCHAR(200) NOT NULL,
    "seq" INT NOT NULL,
    "source_order" INT NOT NULL,
    "heading" VARCHAR(300) NOT NULL DEFAULT '',
    "content" TEXT NOT NULL,
    "search_text" TEXT NOT NULL,
    "embed_text" TEXT NOT NULL,
    "drug_name" VARCHAR(300),
    "source_ids" JSONB NOT NULL,
    "embedding" vector(1536),
    "embedding_model" VARCHAR(50),
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS "idx_evidence_ch_drug_co_e5e252" ON "evidence_chunks" ("drug_code");
CREATE INDEX IF NOT EXISTS "idx_evidence_ch_disease_c59dac" ON "evidence_chunks" ("disease_code");
CREATE INDEX IF NOT EXISTS "idx_evidence_ch_group_k_f72850" ON "evidence_chunks" ("group_key");
COMMENT ON COLUMN "evidence_chunks"."chunk_id" IS '출처 번호 (예: D:641900040:S12, F:HTN:life:나트륨 줄이기). 챗봇이 돌려받는 sentenceId';
COMMENT ON COLUMN "evidence_chunks"."kind" IS 'DRUG: drug\nFACT: fact\nCROSS: cross';
COMMENT ON COLUMN "evidence_chunks"."drug_code" IS '급여 EDI 제품코드 (drug 조각)';
COMMENT ON COLUMN "evidence_chunks"."disease_code" IS '팩트표 질환 id (fact 조각, 예: HTN)';
COMMENT ON COLUMN "evidence_chunks"."section" IS 'E 효능효과 / S 주의사항 / P 용법용량 (drug 조각)';
COMMENT ON COLUMN "evidence_chunks"."group_key" IS '같은 소항목 묶음 키 (후보를 고른 뒤 같은 소항목 문장을 같이 보냄)';
COMMENT ON COLUMN "evidence_chunks"."seq" IS '같은 약, 같은 구분 안에서의 순서';
COMMENT ON COLUMN "evidence_chunks"."source_order" IS '시험에서 쓴 조각 순서 (후보 목록 순서를 같게 하려고 보존)';
COMMENT ON COLUMN "evidence_chunks"."heading" IS '큰제목 > 소항목 경로';
COMMENT ON COLUMN "evidence_chunks"."content" IS '근거 글 원문';
COMMENT ON COLUMN "evidence_chunks"."search_text" IS '글자 조각 검색용 (heading + content)';
COMMENT ON COLUMN "evidence_chunks"."embed_text" IS '임베딩에 넣은 글 (약 이름 + 구분 + 경로 + 본문)';
COMMENT ON COLUMN "evidence_chunks"."drug_name" IS '질문 프롬프트와 근거 머리말에 쓰는 약 이름';
COMMENT ON COLUMN "evidence_chunks"."source_ids" IS '이 조각이 합친 허가정보 문장 번호들 (표를 한 조각으로 푼 경우 여러 개)';
COMMENT ON COLUMN "evidence_chunks"."embedding" IS 'text-embedding-3-small 1536차원';
COMMENT ON COLUMN "evidence_chunks"."embedding_model" IS '벡터를 만든 모델 (바꾸면 새로 만들어야 함)';"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS "evidence_chunks";"""


MODELS_STATE = (
    "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"
)
