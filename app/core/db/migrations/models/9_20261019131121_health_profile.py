from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "user_health_profiles" (
    "smoking" VARCHAR(20) NOT NULL,
    "drinking" VARCHAR(20) NOT NULL,
    "diseases" JSONB NOT NULL,
    "pregnant" VARCHAR(10),
    "dialysis" VARCHAR(10),
    "height_cm" SMALLINT,
    "weight_kg" DECIMAL(4,1),
    "upcoming_exams" JSONB NOT NULL,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "user_id" BIGINT NOT NULL PRIMARY KEY REFERENCES "users" ("id") ON DELETE CASCADE
);
COMMENT ON COLUMN "user_health_profiles"."smoking" IS 'DAILY: daily\nSOMETIMES: sometimes\nPAST: past\nNEVER: never\nUNKNOWN: unknown';
COMMENT ON COLUMN "user_health_profiles"."drinking" IS 'NONE: none\nLT_MONTHLY: lt_monthly\nMONTHLY: monthly\nTWO_FOUR_MONTHLY: 2_4_monthly\nTWO_THREE_WEEKLY: 2_3_weekly\nFOUR_PLUS_WEEKLY: 4plus_weekly\nUNKNOWN: unknown';
COMMENT ON COLUMN "user_health_profiles"."diseases" IS 'lifestyle_diseases.id 목록';
COMMENT ON COLUMN "user_health_profiles"."pregnant" IS '여성만';
COMMENT ON COLUMN "user_health_profiles"."dialysis" IS 'YES: yes\nNO: no\nUNKNOWN: unknown';
COMMENT ON COLUMN "user_health_profiles"."upcoming_exams" IS '[{name, date}] 예정 검사';
COMMENT ON TABLE "user_health_profiles" IS '건강 정보 (users와 1:1, 가입 때 함께 만듦). 동의 철회 · 탈퇴 때 줄째 지움';
        ALTER TABLE "users" DROP COLUMN "nickname";
        ALTER TABLE "analyses" ADD "health_snapshot" JSONB;
        COMMENT ON COLUMN "analyses"."health_snapshot" IS '분석 시점 건강 정보 스냅샷 (U-1 health 모양)';"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "users" ADD "nickname" VARCHAR(50);
        ALTER TABLE "analyses" DROP COLUMN "health_snapshot";
        COMMENT ON COLUMN "users"."nickname" IS '선택 입력. 홈 인사말용';
        DROP TABLE IF EXISTS "user_health_profiles";"""


MODELS_STATE = (
    "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"
)
