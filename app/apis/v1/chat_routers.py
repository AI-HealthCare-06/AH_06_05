"""피처 3 챗봇 (API 명세서 5장 H-1 ~ H-8, #100)"""

from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends
from starlette import status
from starlette.responses import Response

from app.core.errors import AppError
from app.dependencies.security import get_request_user
from app.dtos.chat import ContextCreateRequest, MessageCreateRequest, SessionCreateRequest, SessionTitleRequest
from app.models.users import User
from app.services import chats as svc
from app.services.chatbot import queue as chat_queue

chat_router = APIRouter(prefix="/chat/sessions", tags=["chat"])
CurrentUser = Annotated[User, Depends(get_request_user)]


@chat_router.post("", status_code=status.HTTP_201_CREATED)
async def start_session(body: SessionCreateRequest, user: CurrentUser) -> dict[str, Any]:
    """H-1 대화 시작. 같은 clientRequestId면 새로 만들지 않음. 첫 답은 카드를 붙이는 H-7에서 줌"""
    context = body.context.model_dump() if body.context else None
    return {"sessionId": await svc.start_session(user, body.client_request_id, body.analysis_id, context)}


@chat_router.get("")
async def list_sessions(user: CurrentUser, date: str | None = None, month: str | None = None) -> dict[str, Any]:
    """H-4 날짜별 대화 목록. ?month=는 기록 있는 날짜(CB-02), ?date=는 그날 대화(CB-03). 둘 중 하나만"""
    if bool(date) == bool(month):
        raise AppError(status.HTTP_400_BAD_REQUEST, "VALIDATION_ERROR", "date나 month 하나만 보내 주세요.")
    return await svc.sessions_on(user, date) if date else await svc.days_with_sessions(user, month or "")


@chat_router.get("/today")
async def today(user: CurrentUser) -> dict[str, Any]:
    """H-8 오늘 대화 찾기 (만들지 않음)"""
    return await svc.today(user)


@chat_router.get("/{session_id}/messages")
async def list_messages(session_id: int, user: CurrentUser) -> dict[str, Any]:
    """H-2 이전 대화. 앱이 답을 기다리는 동안 2초마다 부름"""
    return await svc.messages(user, session_id)


@chat_router.post("/{session_id}/messages", status_code=status.HTTP_202_ACCEPTED)
async def ask(
    session_id: int, body: MessageCreateRequest, background: BackgroundTasks, user: CurrentUser
) -> dict[str, Any]:
    """H-3 질문 보내기. 답은 뒤에서 만들고 앱은 H-2로 확인함. 워커에 못 맡기면(꺼짐, 워커 없음) 서버 안에서 만듦 (#118)"""
    message_id, run = await svc.ask(user, session_id, body.content, body.client_request_id, body.emergency_dismissed)
    if run and not await chat_queue.enqueue_answer(message_id, body.emergency_dismissed):
        background.add_task(svc.generate, message_id, body.emergency_dismissed)
    return {"messageId": message_id}


@chat_router.patch("/{session_id}")
async def rename_session(session_id: int, body: SessionTitleRequest, user: CurrentUser) -> dict[str, Any]:
    """H-5 대화 제목 수정"""
    return await svc.rename_session(user, session_id, body.title)


@chat_router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(session_id: int, user: CurrentUser) -> Response:
    """H-6 대화 삭제 (메시지 포함)"""
    await svc.delete_session(user, session_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@chat_router.post("/{session_id}/context", status_code=status.HTTP_201_CREATED)
async def add_context(session_id: int, body: ContextCreateRequest, user: CurrentUser) -> dict[str, Any]:
    """H-7 오늘 대화에 분석 맥락 카드 붙이기. 경고나 약을 고른 카드면 첫 답(firstMessage)도 줌"""
    context = body.context.model_dump() if body.context else None
    return await svc.add_context(user, session_id, body.analysis_id, context, body.client_request_id)
