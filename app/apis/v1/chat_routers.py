"""피처 3 챗봇 (API 명세서 5장 H-1 ~ H-8, #100). H-4, H-5는 2단계"""

from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends
from starlette import status
from starlette.responses import Response

from app.dependencies.security import get_request_user
from app.dtos.chat import ContextCreateRequest, MessageCreateRequest, SessionCreateRequest
from app.models.users import User
from app.services import chats as svc

chat_router = APIRouter(prefix="/chat/sessions", tags=["chat"])
CurrentUser = Annotated[User, Depends(get_request_user)]


@chat_router.post("", status_code=status.HTTP_201_CREATED)
async def start_session(body: SessionCreateRequest, user: CurrentUser) -> dict[str, Any]:
    """H-1 대화 시작. 같은 clientRequestId면 새로 만들지 않음. firstMessage는 아직 없음 (#116)"""
    context = body.context.model_dump() if body.context else None
    return {"sessionId": await svc.start_session(user, body.client_request_id, body.analysis_id, context)}


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
    """H-3 질문 보내기. 답은 뒤에서 만들고 앱은 H-2로 확인함"""
    message_id, run = await svc.ask(user, session_id, body.content, body.client_request_id, body.emergency_dismissed)
    if run:
        background.add_task(svc.generate, message_id, body.emergency_dismissed)
    return {"messageId": message_id}


@chat_router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(session_id: int, user: CurrentUser) -> Response:
    """H-6 대화 삭제 (메시지 포함)"""
    await svc.delete_session(user, session_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@chat_router.post("/{session_id}/context", status_code=status.HTTP_201_CREATED)
async def add_context(session_id: int, body: ContextCreateRequest, user: CurrentUser) -> dict[str, Any]:
    """H-7 오늘 대화에 분석 맥락 카드 붙이기"""
    context = body.context.model_dump() if body.context else None
    await svc.add_context(user, session_id, body.analysis_id, context, body.client_request_id)
    return {}
