from decimal import Decimal

from tortoise.contrib.test import TestCase

from app.models.masters import Disease, DrugProduct
from app.services.drug_names import normalize_name
from app.services.master_loader import parse_disease_rows, parse_drug_row, parse_spec, upsert

ROW = (
    3,
    "내복",
    112,
    112,
    "149203ATB",
    "149203ATB",
    1,
    "doxepin",
    "651904420",
    "명세핀정3밀리그램(독세핀염산염)_(3.39mg/1정)",
    "명인제약(주)",
    "1",
    "정",
    96,
    "전문",
    None,
)


def disease(code: str, name: str, complete: str = "", main: str = "") -> dict:
    return {
        "상병기호": code,
        "한글명": name,
        "영문명": "",
        "완전코드구분": complete,
        "주상병사용구분": main,
        "성별구분": "",
        "상한연령": "",
        "하한연령": "40",
    }


def test_normalize_name_unifies_mg_spelling():
    assert (
        normalize_name("노바스크정5밀리그람(암로디핀베실산염)_(6.944mg/1정)") == "노바스크정5밀리그램(암로디핀베실산염)"
    )
    assert normalize_name("노바스크정5밀리그램(암로디핀베실산염)") == normalize_name("노바스크정 5mg(암로디핀베실산염)")


def test_parse_spec():
    assert parse_spec("95(1)") == Decimal("95")
    assert parse_spec("0.5") == Decimal("0.5")
    assert parse_spec(None) is None


def test_parse_drug_row():
    d = parse_drug_row(ROW)
    assert d["edi_code"] == "651904420"
    assert d["item_name_norm"] == "명세핀정3밀리그램(독세핀염산염)"
    assert d["route"] == "내복" and d["etc_otc"] == "전문" and d["price"] == 96
    assert parse_drug_row((None,) * 16) is None


def test_parse_disease_rows_keeps_first_name():
    rows = parse_disease_rows(
        [
            disease("A000", "비브리오 콜레라"),
            disease("A000", "고전적 콜레라"),
            disease("A00", "콜레라", complete="N", main="N"),
        ]
    )
    assert [r["name_kr"] for r in rows] == ["비브리오 콜레라", "콜레라"]
    assert rows[1]["is_complete"] is False and rows[1]["main_usable"] is False and rows[1]["age_min"] == 40


class TestUpsert(TestCase):
    async def test_upsert_twice_updates_instead_of_duplicating(self):
        d = parse_drug_row(ROW)
        await upsert(DrugProduct, [d], "edi_code")
        await upsert(DrugProduct, [{**d, "price": 120}], "edi_code")
        assert await DrugProduct.filter(edi_code="651904420").count() == 1
        assert (await DrugProduct.get(edi_code="651904420")).price == 120

    async def test_upsert_diseases(self):
        await upsert(Disease, parse_disease_rows([disease("I10", "본태성(일차성) 고혈압")]), "code")
        assert (await Disease.get(code="I10")).name_kr == "본태성(일차성) 고혈압"
