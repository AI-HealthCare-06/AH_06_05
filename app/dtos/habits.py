"""실천 요청 모양 (API 명세서 6장 P-2, P-4). 응답 본문은 서비스가 만든 dict를 그대로 내려줌"""

from datetime import date

from pydantic import Field

from app.dtos.base import CamelModel


class GoalCreateRequest(CamelModel):
    """P-2. 추천 1 ~ 3개 (REQ-111)"""

    recommendation_ids: list[int] = Field(min_length=1, max_length=3)


class RecordCreateRequest(CamelModel):
    """P-4. 체크형은 completed(false면 완료 취소), 수량형은 value(그날 한 총량, 분 등. 다시 보내도 두 번 더해지지 않게, 0이면 취소)"""

    date: date
    completed: bool | None = None
    value: int | None = Field(default=None, ge=0, le=600)
