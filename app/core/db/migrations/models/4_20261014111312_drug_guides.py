from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "drug_guides" (
    "edi_code" VARCHAR(9) NOT NULL PRIMARY KEY,
    "content" JSONB NOT NULL,
    "evidence_ids" JSONB,
    "prompt_ver" VARCHAR(20),
    "model_name" VARCHAR(50),
    "review_status" VARCHAR(20) NOT NULL DEFAULT 'draft',
    "reviewed_by" VARCHAR(50),
    "reviewed_at" TIMESTAMPTZ,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON COLUMN "drug_guides"."content" IS 'category · purpose · caution · source';
COMMENT ON COLUMN "drug_guides"."evidence_ids" IS '근거 번호 (허가정보 · 고시 등)';
COMMENT ON COLUMN "drug_guides"."model_name" IS 'AI 없이 만든 안내문은 null';
COMMENT ON COLUMN "drug_guides"."review_status" IS 'DRAFT: draft\nAPPROVED: approved\nREJECTED: rejected';
COMMENT ON TABLE "drug_guides" IS '약 1개(edi_code)의 복약 안내 중 처방과 상관없는 부분 — 배치로 미리 만들어 두고 분석 때는 조회만 한다 (ERD 추가 제안)';"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS "drug_guides";"""


MODELS_STATE = (
    "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"
)
