from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    # 템플릿 users → ERD v1.3 users. 기존 회원 행을 지우지 않고 칸을 바꿈
    # (성명 · 연락처는 최소 수집 원칙에 따라 버림, 생년월일은 출생연도만 남김)
    return """
        CREATE TABLE IF NOT EXISTS "user_consents" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "consent_type" VARCHAR(30) NOT NULL,
    "agreed" BOOL NOT NULL,
    "agreed_at" TIMESTAMPTZ,
    "withdrawn_at" TIMESTAMPTZ,
    "user_id" BIGINT NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_user_consen_user_id_9f8412" UNIQUE ("user_id", "consent_type")
);
COMMENT ON COLUMN "user_consents"."consent_type" IS 'TERMS: terms\nPRIVACY: privacy\nSENSITIVE_HEALTH: sensitive_health';
COMMENT ON TABLE "user_consents" IS 'CM-02 가입 동의 · CM-05 동의 내역. ERD 복합 unique (user, consent_type)';
        ALTER TABLE "users" RENAME COLUMN "email" TO "login_id";
        ALTER TABLE "users" ALTER COLUMN "login_id" TYPE VARCHAR(100);
        ALTER TABLE "users" ADD CONSTRAINT "users_login_id_key" UNIQUE ("login_id");
        ALTER TABLE "users" RENAME COLUMN "hashed_password" TO "password_hash";
        ALTER TABLE "users" ALTER COLUMN "password_hash" TYPE VARCHAR(255);
        ALTER TABLE "users" ADD "nickname" VARCHAR(50);
        ALTER TABLE "users" ADD "birth_year" SMALLINT;
        UPDATE "users" SET "birth_year" = EXTRACT(YEAR FROM "birthday");
        ALTER TABLE "users" ALTER COLUMN "birth_year" SET NOT NULL;
        ALTER TABLE "users" ADD "sex" VARCHAR(1);
        UPDATE "users" SET "sex" = CASE "gender" WHEN 'MALE' THEN 'M' ELSE 'F' END;
        ALTER TABLE "users" ALTER COLUMN "sex" SET NOT NULL;
        ALTER TABLE "users" ADD "failed_login_count" SMALLINT NOT NULL DEFAULT 0;
        ALTER TABLE "users" ADD "locked_until" TIMESTAMPTZ;
        ALTER TABLE "users" ADD "deleted_at" TIMESTAMPTZ;
        ALTER TABLE "users" DROP COLUMN "name";
        ALTER TABLE "users" DROP COLUMN "gender";
        ALTER TABLE "users" DROP COLUMN "birthday";
        ALTER TABLE "users" DROP COLUMN "phone_number";
        ALTER TABLE "users" DROP COLUMN "is_active";
        ALTER TABLE "users" DROP COLUMN "is_admin";
        ALTER TABLE "users" DROP COLUMN "last_login";
        COMMENT ON COLUMN "users"."login_id" IS '이메일';
COMMENT ON COLUMN "users"."sex" IS 'M: M\nF: F';
COMMENT ON COLUMN "users"."nickname" IS '선택 입력. 홈 인사말용';
COMMENT ON COLUMN "users"."failed_login_count" IS '5번 틀리면 잠금';
COMMENT ON COLUMN "users"."birth_year" IS '노인주의 · 연령금기 판정';
COMMENT ON COLUMN "users"."locked_until" IS '잠금 풀리는 시각';
COMMENT ON COLUMN "users"."deleted_at" IS '탈퇴 시 개인정보를 지우고 시각만 남김';"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    # 되돌릴 때 버린 성명 · 연락처는 빈 값, 생년월일은 출생연도 1월 1일로 채움
    return """
        DROP TABLE IF EXISTS "user_consents";
        ALTER TABLE "users" DROP CONSTRAINT IF EXISTS "users_login_id_key";
        ALTER TABLE "users" RENAME COLUMN "login_id" TO "email";
        ALTER TABLE "users" ALTER COLUMN "email" TYPE VARCHAR(40);
        ALTER TABLE "users" RENAME COLUMN "password_hash" TO "hashed_password";
        ALTER TABLE "users" ALTER COLUMN "hashed_password" TYPE VARCHAR(128);
        ALTER TABLE "users" ADD "name" VARCHAR(20) NOT NULL DEFAULT '';
        ALTER TABLE "users" ADD "gender" VARCHAR(6);
        UPDATE "users" SET "gender" = CASE "sex" WHEN 'M' THEN 'MALE' ELSE 'FEMALE' END;
        ALTER TABLE "users" ALTER COLUMN "gender" SET NOT NULL;
        ALTER TABLE "users" ADD "birthday" DATE;
        UPDATE "users" SET "birthday" = make_date("birth_year", 1, 1);
        ALTER TABLE "users" ALTER COLUMN "birthday" SET NOT NULL;
        ALTER TABLE "users" ADD "phone_number" VARCHAR(11) NOT NULL DEFAULT '';
        ALTER TABLE "users" ADD "is_active" BOOL NOT NULL DEFAULT True;
        ALTER TABLE "users" ADD "is_admin" BOOL NOT NULL DEFAULT False;
        ALTER TABLE "users" ADD "last_login" TIMESTAMPTZ;
        ALTER TABLE "users" DROP COLUMN "nickname";
        ALTER TABLE "users" DROP COLUMN "birth_year";
        ALTER TABLE "users" DROP COLUMN "sex";
        ALTER TABLE "users" DROP COLUMN "failed_login_count";
        ALTER TABLE "users" DROP COLUMN "locked_until";
        ALTER TABLE "users" DROP COLUMN "deleted_at";
        COMMENT ON COLUMN "users"."gender" IS 'MALE: MALE\nFEMALE: FEMALE';"""


MODELS_STATE = (
    "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"
    "VcSQ8xU0XtogqDt4+Fc3g9/sc/Tw6lhg=="
)
