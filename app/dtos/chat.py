"""챗봇 요청 모양 (API 명세서 5장 H-1 ~ H-8). 응답 본문은 서비스가 만든 dict를 그대로 내려줌"""

from typing import Annotated

from pydantic import Field, StringConstraints

from app.dtos.base import CamelModel
from app.models.chat import ContextType

RequestId = Annotated[str, StringConstraints(min_length=1, max_length=64)]


class ChatContext(CamelModel):
    """RG-03 [이 경고 물어보기] (warning), RG-04 [이 약 물어보기] (drug)"""

    type: ContextType
    id: int


class SessionCreateRequest(CamelModel):
    """H-1. analysisId가 없으면 일반 질문 모드"""

    analysis_id: int | None = None
    context: ChatContext | None = None
    client_request_id: RequestId


class MessageCreateRequest(CamelModel):
    """H-3. content는 앞뒤 공백을 지운 뒤 1~500자"""

    content: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
    client_request_id: RequestId
    emergency_dismissed: bool = Field(default=False, description="[지금은 증상이 없어요] 뒤 다시 보낼 때 true")


class ContextCreateRequest(CamelModel):
    """H-7. 오늘 대화에 분석 맥락 카드를 붙임"""

    analysis_id: int
    context: ChatContext | None = None
    client_request_id: RequestId
