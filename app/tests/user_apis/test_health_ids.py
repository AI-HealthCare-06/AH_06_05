from typing import get_args

from app.dtos.users import DiseaseId
from app.services.guide import lifestyle


def test_disease_ids_match_fact_table():
    """내 정보 질환 id = 생활습관 팩트표 질환 id (lifestyle_diseases.id). 팩트표가 바뀌면 같이 고침"""
    assert get_args(DiseaseId) == tuple(d["id"] for d in lifestyle.facts()["diseases"])
