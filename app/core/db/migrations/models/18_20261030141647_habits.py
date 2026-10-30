from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "recommendations" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "challenge_key" VARCHAR(20) NOT NULL,
    "title" VARCHAR(100) NOT NULL,
    "desc" VARCHAR(200),
    "reason_label" VARCHAR(50) NOT NULL,
    "caution_label" VARCHAR(20),
    "goal_type" VARCHAR(20) NOT NULL,
    "target_value" DECIMAL(10,2),
    "unit" VARCHAR(20),
    "fact_refs" JSONB NOT NULL,
    "rank" SMALLINT NOT NULL,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "analysis_id" BIGINT NOT NULL REFERENCES "analyses" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_recommendat_analysi_6fc9aa" UNIQUE ("analysis_id", "challenge_key")
);
COMMENT ON COLUMN "recommendations"."challenge_key" IS 'soup / walk / alcohol (services/challenges.py)';
COMMENT ON COLUMN "recommendations"."desc" IS '팩트표 글 그대로 (예: 하루 소금 5g 이하)';
COMMENT ON COLUMN "recommendations"."reason_label" IS '고혈압, 약과 함께 등 (화면 라벨, 질환 정보)';
COMMENT ON COLUMN "recommendations"."caution_label" IS '의료진이 정한 강도로 (허혈성심질환 걷기)';
COMMENT ON COLUMN "recommendations"."goal_type" IS 'CHECK: check\nQUANTITY: quantity';
COMMENT ON TABLE "recommendations" IS '분석으로 고른 실천 추천 (P-1). 분석을 지우면 같이 지워지고, 이걸 가리키던 목표는 연결만 비움 (R-8)';
        CREATE TABLE IF NOT EXISTS "habit_goals" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "title" VARCHAR(100) NOT NULL,
    "goal_type" VARCHAR(20) NOT NULL,
    "target_value" DECIMAL(10,2),
    "unit" VARCHAR(20),
    "start_date" DATE NOT NULL,
    "end_date" DATE,
    "status" VARCHAR(20) NOT NULL DEFAULT 'active',
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "recommendation_id" BIGINT REFERENCES "recommendations" ("id") ON DELETE SET NULL,
    "user_id" BIGINT NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE
);
COMMENT ON COLUMN "habit_goals"."goal_type" IS 'CHECK: check\nQUANTITY: quantity';
COMMENT ON COLUMN "habit_goals"."end_date" IS '끝낸 날 (새로 고르거나 동의 철회)';
COMMENT ON COLUMN "habit_goals"."status" IS 'ACTIVE: active\nENDED: ended';
COMMENT ON TABLE "habit_goals" IS '사용자가 고른 실천 목표 (P-2). 활성 목표는 최대 3개 (REQ-111)';
        CREATE TABLE IF NOT EXISTS "habit_records" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "record_date" DATE NOT NULL,
    "value" DECIMAL(10,2),
    "completed" BOOL NOT NULL DEFAULT False,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "goal_id" BIGINT NOT NULL REFERENCES "habit_goals" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_habit_recor_goal_id_cd7dd7" UNIQUE ("goal_id", "record_date")
);
COMMENT ON TABLE "habit_records" IS '하루 실천 기록 (P-4). 수량형은 그날 쌓인 값';"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS "habit_goals";
        DROP TABLE IF EXISTS "habit_records";
        DROP TABLE IF EXISTS "recommendations";"""


MODELS_STATE = (
    "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"
)
