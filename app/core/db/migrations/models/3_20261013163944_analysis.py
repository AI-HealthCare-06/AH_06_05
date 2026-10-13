from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "analyses" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "status" VARCHAR(20) NOT NULL DEFAULT 'queued',
    "current_step" VARCHAR(30),
    "failed_step" VARCHAR(30),
    "error_code" VARCHAR(50),
    "retry_count" SMALLINT NOT NULL DEFAULT 0,
    "user_birth_year" SMALLINT,
    "started_at" TIMESTAMPTZ,
    "finished_at" TIMESTAMPTZ,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "user_id" BIGINT NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE
);
COMMENT ON COLUMN "analyses"."status" IS 'QUEUED: queued\nRUNNING: running\nDONE: done\nFAILED: failed';
COMMENT ON COLUMN "analyses"."current_step" IS 'RG-01 진행 단계';
COMMENT ON COLUMN "analyses"."failed_step" IS '실패한 단계 (RG-01-E1)';
COMMENT ON COLUMN "analyses"."error_code" IS 'GUIDE_GENERATION_FAILED / SAFETY_CHECK_FAILED / TIMEOUT';
COMMENT ON COLUMN "analyses"."retry_count" IS '3회 초과 시 재시도 막음 (REQ-055)';
COMMENT ON COLUMN "analyses"."user_birth_year" IS '분석 시점 출생연도 스냅샷';
        CREATE TABLE IF NOT EXISTS "analysis_diseases" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "origin" VARCHAR(20) NOT NULL,
    "analysis_id" BIGINT NOT NULL REFERENCES "analyses" ("id") ON DELETE CASCADE,
    "disease_id" VARCHAR(10) NOT NULL REFERENCES "diseases" ("code") ON DELETE RESTRICT,
    CONSTRAINT "uid_analysis_di_analysi_205456" UNIQUE ("analysis_id", "disease_id")
);
COMMENT ON COLUMN "analysis_diseases"."origin" IS 'PRESCRIPTION: prescription\nUSER: user';
COMMENT ON TABLE "analysis_diseases" IS '생활습관 가이드 조회 기준 질환. ERD 복합 PK → id + unique';
        CREATE TABLE IF NOT EXISTS "analysis_prescriptions" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "analysis_id" BIGINT NOT NULL REFERENCES "analyses" ("id") ON DELETE CASCADE,
    "prescription_id" BIGINT NOT NULL REFERENCES "prescriptions" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_analysis_pr_analysi_b18f54" UNIQUE ("analysis_id", "prescription_id")
);
COMMENT ON TABLE "analysis_prescriptions" IS '분석에 쓴 처방전 (여러 병원 처방전을 한 번에 점검). ERD 복합 PK → id + unique';
        CREATE TABLE IF NOT EXISTS "analysis_warnings" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "warning_type" VARCHAR(30) NOT NULL,
    "severity" VARCHAR(10) NOT NULL,
    "reason" TEXT,
    "summary" TEXT,
    "source" VARCHAR(100),
    "notice_date" DATE,
    "daily_total" DECIMAL(12,3),
    "max_daily" DECIMAL(12,3),
    "detail" JSONB,
    "analysis_id" BIGINT NOT NULL REFERENCES "analyses" ("id") ON DELETE CASCADE,
    "item_id_a" BIGINT REFERENCES "prescription_items" ("id") ON DELETE SET NULL,
    "item_id_b" BIGINT REFERENCES "prescription_items" ("id") ON DELETE SET NULL
);
COMMENT ON COLUMN "analysis_warnings"."reason" IS 'DUR 금기 사유 원문';
COMMENT ON COLUMN "analysis_warnings"."summary" IS '화면 표시 문장 (템플릿, AI 생성 아님 · NFR-032)';
COMMENT ON COLUMN "analysis_warnings"."source" IS '고시명';
COMMENT ON COLUMN "analysis_warnings"."daily_total" IS '1일 최대용량 초과일 때만';
COMMENT ON COLUMN "analysis_warnings"."detail" IS '(ERD 추가 제안) 약이 3개 이상인 경고의 전체 항목 번호 · 성분 · 근거 구분';
COMMENT ON TABLE "analysis_warnings" IS 'DB 조회로 결정적으로 산출한 경고. 0건이면 RG-02-E1';
        CREATE TABLE IF NOT EXISTS "guides" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "section" VARCHAR(30) NOT NULL,
    "status" VARCHAR(20) NOT NULL,
    "content" JSONB,
    "prompt_ver" VARCHAR(20),
    "model_name" VARCHAR(50),
    "tts_url" VARCHAR(500),
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "analysis_id" BIGINT NOT NULL REFERENCES "analyses" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_guides_analysi_6aeb60" UNIQUE ("analysis_id", "section")
);
COMMENT ON COLUMN "guides"."section" IS 'MEDICATION: medication\nLIFESTYLE: lifestyle';
COMMENT ON COLUMN "guides"."status" IS 'DONE: done\nFAILED: failed';
COMMENT ON COLUMN "guides"."model_name" IS 'AI 없이 만든 안내문은 null';
COMMENT ON TABLE "guides" IS '안내문 — 항목 고정 JSON (결과 일관성 NFR-030)';"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS "analysis_warnings";
        DROP TABLE IF EXISTS "analysis_prescriptions";
        DROP TABLE IF EXISTS "analyses";
        DROP TABLE IF EXISTS "guides";
        DROP TABLE IF EXISTS "analysis_diseases";"""


MODELS_STATE = (
    "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"
    "xhrWOGEn78H5OcopE="
)
