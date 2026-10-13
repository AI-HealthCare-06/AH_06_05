"""분석 요청 · 응답 모양 — API 명세서 4장 (R-1 ~ R-6). 결과 본문(R-4 · R-5 · R-6)은 서비스가 만든 dict를 그대로 내려줌"""

from pydantic import Field

from app.dtos.base import CamelModel


class AnalysisCreateRequest(CamelModel):
    prescription_ids: list[int] = Field(min_length=1, max_length=5)


class AnalysisCreatedResponse(CamelModel):
    analysis_id: int
    status: str


class DiseasesRequest(CamelModel):
    """빈 배열 = 해당 없음 · 모르겠어요"""

    disease_codes: list[str] = Field(max_length=10)
