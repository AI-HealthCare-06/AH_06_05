from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "chat_sessions" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "context_type" VARCHAR(20),
    "context_ref" BIGINT,
    "title" VARCHAR(100),
    "summary" TEXT,
    "client_request_id" VARCHAR(64),
    "safety_mode_until" TIMESTAMPTZ,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "analysis_id" BIGINT REFERENCES "analyses" ("id") ON DELETE SET NULL,
    "user_id" BIGINT NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_chat_sessio_user_id_0e1863" UNIQUE ("user_id", "client_request_id")
);
COMMENT ON COLUMN "chat_sessions"."context_type" IS 'WARNING: warning\nDRUG: drug';
COMMENT ON COLUMN "chat_sessions"."context_ref" IS 'analysis_warnings.id 또는 prescription_items.id';
COMMENT ON COLUMN "chat_sessions"."title" IS '2단계 CB-03';
COMMENT ON COLUMN "chat_sessions"."summary" IS '오래된 대화 요약 (2단계)';
COMMENT ON COLUMN "chat_sessions"."client_request_id" IS 'H-1을 다시 보내도 대화를 새로 만들지 않음';
COMMENT ON COLUMN "chat_sessions"."safety_mode_until" IS '자해 표현 뒤 안전 모드가 끝나는 시각. 1단계는 그날 자정 (H-8)';
        CREATE TABLE IF NOT EXISTS "chat_messages" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "role" VARCHAR(10) NOT NULL,
    "content" TEXT NOT NULL,
    "answer_type" VARCHAR(20),
    "sources" JSONB,
    "client_request_id" VARCHAR(64),
    "context_card" JSONB,
    "safety_card" JSONB,
    "safety" JSONB,
    "status" VARCHAR(20) NOT NULL DEFAULT 'done',
    "model" VARCHAR(50),
    "prompt_tokens" INT,
    "completion_tokens" INT,
    "latency_ms" INT,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "session_id" BIGINT NOT NULL REFERENCES "chat_sessions" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_chat_messag_session_91af02" UNIQUE ("session_id", "client_request_id")
);
COMMENT ON COLUMN "chat_messages"."role" IS 'USER: user\nASSISTANT: assistant';
COMMENT ON COLUMN "chat_messages"."content" IS '1층이 잡은 질문은 빈 글 (원문 저장하지 않음)';
COMMENT ON COLUMN "chat_messages"."answer_type" IS 'NORMAL: normal\nCLARIFY: clarify\nPARTIAL: partial\nNO_EVIDENCE: no_evidence\nREFER: refer\nEMERGENCY: emergency\nCRISIS: crisis';
COMMENT ON COLUMN "chat_messages"."sources" IS '[{ title, basedOn }]';
COMMENT ON COLUMN "chat_messages"."client_request_id" IS '질문 줄만. 다시 시도 때 두 번 저장하지 않음';
COMMENT ON COLUMN "chat_messages"."context_card" IS 'H-7 맥락 카드 { analysisId, context }';
COMMENT ON COLUMN "chat_messages"."safety_card" IS '{ analysisId, warningIds }. 답은 normal';
COMMENT ON COLUMN "chat_messages"."safety" IS '{ types, overdose, rule }. 원문 없음';
COMMENT ON COLUMN "chat_messages"."status" IS 'GENERATING: generating\nDONE: done';
COMMENT ON COLUMN "chat_messages"."model" IS '답 줄만';
COMMENT ON COLUMN "chat_messages"."latency_ms" IS '질문을 받은 때부터 답을 저장할 때까지';"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS "chat_sessions";
        DROP TABLE IF EXISTS "chat_messages";"""


MODELS_STATE = (
    "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"
    "+Q=="
)
