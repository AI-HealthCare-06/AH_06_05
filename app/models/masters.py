"""공공데이터 마스터 (ERD v1.3 마스터 영역) — 요청 때 API를 부르지 않고 미리 넣어 둠"""

from tortoise import fields, models


class DrugProduct(models.Model):
    """심평원 약제급여목록 1품목 = 1행. edi_code = 식약처 EDI_CODE (조인 키)"""

    edi_code = fields.CharField(max_length=9, primary_key=True)
    item_seq = fields.CharField(max_length=9, null=True, description="식약처 품목기준코드")
    item_name = fields.CharField(max_length=300)
    item_name_norm = fields.CharField(max_length=300, null=True, db_index=True, description="정규화된 이름 — 매칭용")
    entp_name = fields.CharField(max_length=200, null=True)
    ingr_code = fields.CharField(max_length=9, null=True, db_index=True, description="심평원 주성분코드")
    ingr_group = fields.CharField(max_length=9, null=True, description="주성분코드_동일제형")
    etc_otc = fields.CharField(max_length=10, null=True, description="전문 / 일반")
    class_code = fields.CharField(max_length=10, null=True, description="약효분류")
    spec_value = fields.DecimalField(
        max_digits=12, decimal_places=3, null=True, description="포장 규격 숫자 (예: 1, 95(1) → 95) — 성분 함량 아님"
    )
    spec_unit = fields.CharField(max_length=30, null=True, description="포장 단위 (예: 정, mL/병)")
    price = fields.IntField(null=True, description="급여 상한금액")
    route = fields.CharField(max_length=10, null=True, description="내복 / 주사 / 외용")

    class Meta:
        table = "drug_products"


class Disease(models.Model):
    """심평원 상병마스터 (KCD)"""

    code = fields.CharField(max_length=10, primary_key=True)
    name_kr = fields.CharField(max_length=300)
    name_en = fields.CharField(max_length=500, null=True)
    is_complete = fields.BooleanField(null=True, description="완전코드 여부")
    main_usable = fields.BooleanField(null=True, description="주상병 사용 가능 여부")
    sex_limit = fields.CharField(max_length=1, null=True)
    age_min = fields.SmallIntField(null=True)
    age_max = fields.SmallIntField(null=True)

    class Meta:
        table = "diseases"
