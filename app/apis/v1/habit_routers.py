"""피처 4 실천 (API 명세서 6장 P-1 ~ P-4). P-5 달성 현황, P-6 포인트는 뒤로 미룸"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from starlette import status

from app.dependencies.security import get_request_user
from app.dtos.habits import GoalCreateRequest, RecordCreateRequest
from app.models.users import User
from app.services import habits as svc

recommendation_router = APIRouter(prefix="/recommendations", tags=["habits"])
habit_router = APIRouter(prefix="/habit-goals", tags=["habits"])
CurrentUser = Annotated[User, Depends(get_request_user)]


@recommendation_router.get("")
async def recommendations(analysis_id: Annotated[int, Query(alias="analysisId")], user: CurrentUser) -> dict[str, Any]:
    """P-1 생활습관 추천 (RG-05 → RW-02). 질환이 없으면 items가 비고 hasDiseases가 false"""
    return await svc.recommendations(user, analysis_id)


@habit_router.post("", status_code=status.HTTP_201_CREATED)
async def create_goals(body: GoalCreateRequest, user: CurrentUser) -> dict[str, Any]:
    """P-2 목표 만들기 (RW-02)"""
    return {"goalIds": await svc.create_goals(user, body.recommendation_ids)}


@habit_router.get("/today")
async def today(user: CurrentUser) -> dict[str, Any]:
    """P-3 오늘의 실천 (홈 카드, RW-03). hasGoals가 false면 RW-03-E2"""
    return await svc.today_view(user)


@habit_router.post("/{goal_id}/records")
async def record(goal_id: int, body: RecordCreateRequest, user: CurrentUser) -> dict[str, Any]:
    """P-4 실천 기록 (RW-03). 실패하면 앱은 RW-03-E1 배너와 같은 요청 다시 보내기"""
    return await svc.record(user, goal_id, body.date, body.completed, body.value)
