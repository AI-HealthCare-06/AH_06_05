"""챗봇 대화와 메시지 DB 읽기, 쓰기 (#100). 주인 확인은 대화를 꺼낼 때 user로 거름"""

from datetime import datetime
from typing import Any

from tortoise.transactions import in_transaction

from app.models.chat import AnswerType, ChatMessage, ChatSession, MessageRole, MessageStatus
from app.models.users import User


class ChatRepository:
    # ── 대화 ──
    async def get_session(self, user: User, session_id: int) -> ChatSession | None:
        return await ChatSession.get_or_none(id=session_id, user=user)

    async def get_session_by_request(self, user: User, client_request_id: str) -> ChatSession | None:
        return await ChatSession.get_or_none(user=user, client_request_id=client_request_id)

    async def create_session(self, user: User, client_request_id: str, **fields: Any) -> ChatSession:
        return await ChatSession.create(user=user, client_request_id=client_request_id, **fields)

    async def last_session_since(self, user: User, since: datetime) -> ChatSession | None:
        return await ChatSession.filter(user=user, created_at__gte=since).order_by("-id").first()

    async def has_session(self, user: User) -> bool:
        return await ChatSession.filter(user=user).exists()

    async def delete_session(self, session: ChatSession) -> None:
        await session.delete()  # 메시지는 DB가 같이 지움 (ON DELETE CASCADE)

    async def set_safety_mode(self, session_id: int, until: datetime) -> None:
        await ChatSession.filter(id=session_id).update(safety_mode_until=until)

    # ── 메시지 ──
    async def messages(self, session: ChatSession) -> list[ChatMessage]:
        return await ChatMessage.filter(session=session).order_by("id")

    async def done_messages_before(self, session_id: int, message_id: int) -> list[ChatMessage]:
        return await ChatMessage.filter(session_id=session_id, id__lt=message_id, status=MessageStatus.DONE).order_by(
            "id"
        )

    async def get_by_request(self, session: ChatSession, client_request_id: str) -> ChatMessage | None:
        return await ChatMessage.get_or_none(session=session, client_request_id=client_request_id)

    async def last_answer_to(self, question: ChatMessage) -> ChatMessage | None:
        return await ChatMessage.filter(reply_to=question).order_by("-id").first()

    async def last_card_analysis(self, session: ChatSession) -> int | None:
        card = await ChatMessage.filter(session=session, context_card__not_isnull=True).order_by("-id").first()
        return card.context_card.get("analysisId") if card else None

    async def create_card(self, session: ChatSession, client_request_id: str, card: dict[str, Any]) -> ChatMessage:
        return await ChatMessage.create(
            session=session, role=MessageRole.ASSISTANT, client_request_id=client_request_id, context_card=card
        )

    async def create_question_and_answer(
        self, session: ChatSession, content: str, client_request_id: str, **answer: Any
    ) -> ChatMessage:
        """질문 줄과 답 줄을 한 번에 만듦. 답 줄을 돌려줌"""
        async with in_transaction():
            q = await ChatMessage.create(
                session=session, role=MessageRole.USER, content=content, client_request_id=client_request_id
            )
            return await ChatMessage.create(session=session, role=MessageRole.ASSISTANT, reply_to=q, **answer)

    async def create_generating(self, question: ChatMessage) -> ChatMessage:
        return await ChatMessage.create(
            session_id=question.session_id,
            role=MessageRole.ASSISTANT,
            status=MessageStatus.GENERATING,
            reply_to=question,
        )

    async def get_generating(self, message_id: int) -> ChatMessage | None:
        return await ChatMessage.get_or_none(id=message_id, status=MessageStatus.GENERATING).prefetch_related(
            "reply_to", "session__user"
        )

    async def delete_message(self, message_id: int) -> None:
        await ChatMessage.filter(id=message_id).delete()

    async def finish(self, message_id: int, answer_type: AnswerType, **fields: Any) -> bool:
        """만드는 중인 답 줄에만 저장. 그사이 지워졌으면(30초 정리) False"""
        n = await ChatMessage.filter(id=message_id, status=MessageStatus.GENERATING).update(
            status=MessageStatus.DONE, answer_type=answer_type, **fields
        )
        return bool(n)
