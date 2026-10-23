"""피처 3 챗봇, 대화와 메시지 (ERD v1.5 초안 챗봇 영역, API H-1 ~ H-8)

1단계는 하루 한 대화. 질문 줄과 답 줄을 같은 표에 두고, 답 줄은 reply_to로 질문 줄을 가리킴.
1층이 잡은 질문은 원문을 저장하지 않음 (content 빈 글, 설계 메모 4-6).
"""

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from tortoise import fields, models

if TYPE_CHECKING:
    from app.models.analysis import Analysis
    from app.models.users import User


class ContextType(StrEnum):
    WARNING = "warning"  # RG-03 [이 경고 챗봇에 물어보기]
    DRUG = "drug"  # RG-04 [이 약 챗봇에 물어보기]


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class MessageStatus(StrEnum):
    GENERATING = "generating"  # 답을 만드는 중. 실패하면 줄을 지움 (failed는 두지 않음)
    DONE = "done"


class AnswerType(StrEnum):
    """CB-01 말풍선 라벨과 1:1 (명세서 H-3). error는 앱 전용이라 저장하지 않음"""

    NORMAL = "normal"
    CLARIFY = "clarify"
    PARTIAL = "partial"
    NO_EVIDENCE = "no_evidence"
    REFER = "refer"
    EMERGENCY = "emergency"
    CRISIS = "crisis"


class ChatSession(models.Model):
    id = fields.BigIntField(primary_key=True)
    user: fields.ForeignKeyRelation["User"] = fields.ForeignKeyField(
        "models.User", related_name="chat_sessions", on_delete=fields.CASCADE
    )
    # 분석을 지우면(R-8) 이 대화는 R-8 코드가 지움 (그 분석의 맥락 카드가 붙은 대화도, #119 리뷰 10/23). FK는 set null
    analysis: fields.ForeignKeyNullableRelation["Analysis"] = fields.ForeignKeyField(
        "models.Analysis", related_name="chat_sessions", null=True, on_delete=fields.SET_NULL
    )
    context_type = fields.CharEnumField(enum_type=ContextType, max_length=20, null=True)
    context_ref = fields.BigIntField(null=True, description="analysis_warnings.id 또는 prescription_items.id")
    title = fields.CharField(max_length=100, null=True, description="2단계 CB-03")
    summary = fields.TextField(null=True, description="오래된 대화 요약 (2단계)")
    client_request_id = fields.CharField(
        max_length=64, null=True, description="H-1을 다시 보내도 대화를 새로 만들지 않음"
    )
    safety_mode_until: datetime | None = fields.DatetimeField(
        null=True, description="자해 표현 뒤 안전 모드가 끝나는 시각. 1단계는 그날 자정 (H-8)"
    )
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)
    analysis_id: int | None  # 외래 키 칸 (타입 검사용, 칸을 새로 만들지 않음)

    class Meta:
        table = "chat_sessions"
        unique_together = (("user", "client_request_id"),)


class ChatMessage(models.Model):
    id = fields.BigIntField(primary_key=True)
    session: fields.ForeignKeyRelation[ChatSession] = fields.ForeignKeyField(
        "models.ChatSession", related_name="messages", on_delete=fields.CASCADE
    )
    role = fields.CharEnumField(enum_type=MessageRole, max_length=10)
    content = fields.TextField(default="", description="1층이 잡은 질문은 빈 글 (원문 저장하지 않음)")
    answer_type = fields.CharEnumField(enum_type=AnswerType, max_length=20, null=True)
    sources: Any = fields.JSONField(null=True, description="[{ title, basedOn }]")
    client_request_id = fields.CharField(
        max_length=64, null=True, description="질문 줄만. 다시 시도 때 두 번 저장하지 않음"
    )
    reply_to: fields.ForeignKeyNullableRelation["ChatMessage"] = fields.ForeignKeyField(
        "models.ChatMessage", related_name="replies", null=True, on_delete=fields.SET_NULL,
        description="답 줄만. 어느 질문의 답인지",
    )  # fmt: skip
    context_card: Any = fields.JSONField(null=True, description="H-7 맥락 카드 { analysisId, context }")
    safety_card: Any = fields.JSONField(null=True, description="{ analysisId, warningIds }. 답은 normal")
    safety: Any = fields.JSONField(null=True, description="{ types, overdose, rule }. 원문 없음")
    status = fields.CharEnumField(enum_type=MessageStatus, max_length=20, default=MessageStatus.DONE)
    model = fields.CharField(max_length=50, null=True, description="답 줄만")
    prompt_tokens = fields.IntField(null=True)
    completion_tokens = fields.IntField(null=True)
    latency_ms = fields.IntField(null=True, description="질문을 받은 때부터 답을 저장할 때까지")
    created_at = fields.DatetimeField(auto_now_add=True)
    session_id: int  # 외래 키 칸 (타입 검사용, 칸을 새로 만들지 않음)
    reply_to_id: int | None

    class Meta:
        table = "chat_messages"
        unique_together = (("session", "client_request_id"),)
