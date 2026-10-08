from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "diseases" (
    "code" VARCHAR(10) NOT NULL PRIMARY KEY,
    "name_kr" VARCHAR(300) NOT NULL,
    "name_en" VARCHAR(500),
    "is_complete" BOOL,
    "main_usable" BOOL,
    "sex_limit" VARCHAR(1),
    "age_min" SMALLINT,
    "age_max" SMALLINT
);
COMMENT ON COLUMN "diseases"."is_complete" IS '완전코드 여부';
COMMENT ON COLUMN "diseases"."main_usable" IS '주상병 사용 가능 여부';
COMMENT ON TABLE "diseases" IS '심평원 상병마스터 (KCD)';
        CREATE TABLE IF NOT EXISTS "drug_products" (
    "edi_code" VARCHAR(9) NOT NULL PRIMARY KEY,
    "item_seq" VARCHAR(9),
    "item_name" VARCHAR(300) NOT NULL,
    "item_name_norm" VARCHAR(300),
    "entp_name" VARCHAR(200),
    "ingr_code" VARCHAR(9),
    "ingr_group" VARCHAR(9),
    "etc_otc" VARCHAR(10),
    "class_code" VARCHAR(10),
    "spec_value" DECIMAL(12,3),
    "spec_unit" VARCHAR(30),
    "price" INT,
    "route" VARCHAR(10)
);
CREATE INDEX IF NOT EXISTS "idx_drug_produc_item_na_d44628" ON "drug_products" ("item_name_norm");
CREATE INDEX IF NOT EXISTS "idx_drug_produc_ingr_co_d1db68" ON "drug_products" ("ingr_code");
COMMENT ON COLUMN "drug_products"."item_seq" IS '식약처 품목기준코드';
COMMENT ON COLUMN "drug_products"."item_name_norm" IS '정규화된 이름 — 매칭용';
COMMENT ON COLUMN "drug_products"."ingr_code" IS '심평원 주성분코드';
COMMENT ON COLUMN "drug_products"."ingr_group" IS '주성분코드_동일제형';
COMMENT ON COLUMN "drug_products"."etc_otc" IS '전문 / 일반';
COMMENT ON COLUMN "drug_products"."class_code" IS '약효분류';
COMMENT ON COLUMN "drug_products"."spec_value" IS '포장 규격 숫자 (예: 1, 95(1) → 95) — 성분 함량 아님';
COMMENT ON COLUMN "drug_products"."spec_unit" IS '포장 단위 (예: 정, mL/병)';
COMMENT ON COLUMN "drug_products"."price" IS '급여 상한금액';
COMMENT ON COLUMN "drug_products"."route" IS '내복 / 주사 / 외용';
COMMENT ON TABLE "drug_products" IS '심평원 약제급여목록 1품목 = 1행. edi_code = 식약처 EDI_CODE (조인 키)';
        CREATE TABLE IF NOT EXISTS "ocr_jobs" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "status" VARCHAR(20) NOT NULL DEFAULT 'queued',
    "file_count" SMALLINT NOT NULL,
    "error_code" VARCHAR(50),
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "finished_at" TIMESTAMPTZ,
    "user_id" BIGINT NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE
);
COMMENT ON COLUMN "ocr_jobs"."status" IS 'QUEUED: queued\nRUNNING: running\nDONE: done\nFAILED: failed';
COMMENT ON COLUMN "ocr_jobs"."file_count" IS '한 번에 올린 사진 수 (최대 5)';
COMMENT ON COLUMN "ocr_jobs"."error_code" IS '전체 실패 시 OCR_FAILED 등';
COMMENT ON TABLE "ocr_jobs" IS 'O-1 업로드 = 작업 1개 (사진 최대 5장). O-5로 상태 조회';
        CREATE TABLE IF NOT EXISTS "prescriptions" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "file_index" SMALLINT,
    "doc_type" VARCHAR(20) NOT NULL,
    "issued_date" DATE,
    "hospital_name" VARCHAR(200),
    "ocr_raw_text" TEXT,
    "ocr_confidence" DECIMAL(5,4),
    "quality_flag" VARCHAR(20),
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "ocr_job_id" BIGINT REFERENCES "ocr_jobs" ("id") ON DELETE SET NULL,
    "user_id" BIGINT NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE
);
COMMENT ON COLUMN "prescriptions"."file_index" IS '작업 안에서 몇 번째 사진인지';
COMMENT ON COLUMN "prescriptions"."doc_type" IS 'PRESCRIPTION: prescription\nPILL_BAG: pill_bag';
COMMENT ON COLUMN "prescriptions"."issued_date" IS '처방 교부일';
COMMENT ON COLUMN "prescriptions"."ocr_raw_text" IS 'OCR 원문 — 암호화 저장 예정 (원본 이미지는 저장 안 함)';
COMMENT ON COLUMN "prescriptions"."quality_flag" IS 'OK: ok\nLOW: low';
        CREATE TABLE IF NOT EXISTS "prescription_diseases" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "is_main" BOOL NOT NULL DEFAULT False,
    "disease_id" VARCHAR(10) NOT NULL REFERENCES "diseases" ("code") ON DELETE RESTRICT,
    "prescription_id" BIGINT NOT NULL REFERENCES "prescriptions" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_prescriptio_prescri_11b105" UNIQUE ("prescription_id", "disease_id")
);
COMMENT ON COLUMN "prescription_diseases"."is_main" IS '주상병 여부';
COMMENT ON TABLE "prescription_diseases" IS '처방전 질병분류기호 (주상병 + 부상병 여러 개). ERD 복합 PK → id + unique';
        CREATE TABLE IF NOT EXISTS "prescription_items" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "raw_name" VARCHAR(300) NOT NULL,
    "match_score" DECIMAL(5,4),
    "match_status" VARCHAR(20) NOT NULL,
    "dose_per_time" DECIMAL(10,3),
    "times_per_day" SMALLINT,
    "total_days" SMALLINT,
    "timing" VARCHAR(50),
    "edi_code" VARCHAR(9) REFERENCES "drug_products" ("edi_code") ON DELETE RESTRICT,
    "prescription_id" BIGINT NOT NULL REFERENCES "prescriptions" ("id") ON DELETE CASCADE
);
COMMENT ON COLUMN "prescription_items"."raw_name" IS 'OCR이 읽은 원문 약품명';
COMMENT ON COLUMN "prescription_items"."match_status" IS 'AUTO: auto\nNEEDS_CONFIRM: needs_confirm\nUSER_CONFIRMED: user_confirmed\nUNMATCHED: unmatched\nEXCLUDED: excluded';
COMMENT ON COLUMN "prescription_items"."timing" IS '아침 식후 등';
COMMENT ON COLUMN "prescription_items"."edi_code" IS '매칭 실패 · 제외 시 null';
COMMENT ON TABLE "prescription_items" IS '처방 약 1줄. needs_confirm · unmatched가 남으면 분석 시작 불가 (REQ-033)';
        CREATE TABLE IF NOT EXISTS "prescription_item_candidates" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "rank" SMALLINT NOT NULL,
    "score" DECIMAL(5,4),
    "edi_code" VARCHAR(9) NOT NULL REFERENCES "drug_products" ("edi_code") ON DELETE RESTRICT,
    "item_id" BIGINT NOT NULL REFERENCES "prescription_items" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_prescriptio_item_id_d2a503" UNIQUE ("item_id", "rank")
);
COMMENT ON TABLE "prescription_item_candidates" IS 'OC-02 후보 목록 (1순위 적중률 · 5순위 내 포함률 측정용). ERD 복합 PK → id + unique';"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS "prescription_item_candidates";
        DROP TABLE IF EXISTS "prescription_items";
        DROP TABLE IF EXISTS "prescription_diseases";
        DROP TABLE IF EXISTS "prescriptions";
        DROP TABLE IF EXISTS "ocr_jobs";
        DROP TABLE IF EXISTS "drug_products";
        DROP TABLE IF EXISTS "diseases";"""


MODELS_STATE = (
    "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"
    "zD6/Hf/wGLACCg"
)
