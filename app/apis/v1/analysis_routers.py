"""피처 2 RAG 분석 — R-1 ~ R-9 (API 명세서 4장)"""

from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from starlette import status
from starlette.responses import Response

from app.dependencies.security import get_request_user
from app.dtos.analysis import (
    AnalysisCreatedResponse,
    AnalysisCreateRequest,
    DiseasesRequest,
    GuideFeedbackRequest,
    GuideFeedbackResponse,
)
from app.models.users import User
from app.services import analyses as svc

analysis_router = APIRouter(prefix="/analyses", tags=["analysis"])
guide_router = APIRouter(prefix="/guides", tags=["analysis"])
CurrentUser = Annotated[User, Depends(get_request_user)]


@analysis_router.post("", response_model=AnalysisCreatedResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_analysis(
    body: AnalysisCreateRequest, background: BackgroundTasks, user: CurrentUser
) -> AnalysisCreatedResponse:
    """R-1 — 확인이 끝난 처방전(최대 5장)을 합쳐서 점검. 분석은 뒤에서 진행"""
    analysis = await svc.create_analysis(user, body.prescription_ids)
    background.add_task(svc.run_analysis, analysis.id)
    return AnalysisCreatedResponse(analysis_id=analysis.id, status="queued")


@analysis_router.get("/{analysis_id}/status")
async def analysis_status(analysis_id: int, user: CurrentUser) -> dict[str, Any]:
    """R-2 — 2초 간격 폴링"""
    return await svc.get_status(user, analysis_id)


@analysis_router.post(
    "/{analysis_id}/retry", response_model=AnalysisCreatedResponse, status_code=status.HTTP_202_ACCEPTED
)
async def retry_analysis(analysis_id: int, background: BackgroundTasks, user: CurrentUser) -> AnalysisCreatedResponse:
    """R-3 — 실패한 단계부터 다시 (3회까지)"""
    analysis, start = await svc.prepare_retry(user, analysis_id)
    background.add_task(svc.run_analysis, analysis.id, start)
    return AnalysisCreatedResponse(analysis_id=analysis.id, status="queued")


@analysis_router.get("/{analysis_id}")
async def get_analysis(analysis_id: int, user: CurrentUser) -> dict[str, Any]:
    """R-4 — 탭 3개(안전성 · 복약 · 생활습관) 한 번에"""
    return await svc.get_result(user, analysis_id)


@analysis_router.get("/{analysis_id}/warnings/{warning_id}")
async def get_warning_detail(analysis_id: int, warning_id: int, user: CurrentUser) -> dict[str, Any]:
    """R-5 — 경고 자세히"""
    return await svc.get_warning(user, analysis_id, warning_id)


@analysis_router.put("/{analysis_id}/diseases")
async def put_diseases(analysis_id: int, body: DiseasesRequest, user: CurrentUser) -> dict[str, Any]:
    """R-6 — 질환을 직접 골라 생활습관 안내만 다시 만듦"""
    return await svc.put_diseases(user, analysis_id, body.disease_codes)


@analysis_router.get("")
async def list_analyses(
    user: CurrentUser,
    cursor: Annotated[str | None, Query()] = None,
    size: Annotated[int, Query(ge=1, le=svc.LIST_MAX_SIZE)] = svc.LIST_DEFAULT_SIZE,
) -> dict[str, Any]:
    """R-7 — 지난 기록 목록 (홈은 size=1로 최근 1건)"""
    return await svc.list_analyses(user, cursor, size)


@analysis_router.delete("/{analysis_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_analysis(analysis_id: int, user: CurrentUser) -> Response:
    """R-8 — 기록 삭제 (결과 · 경고 · 안내문 · 피드백과 이 분석에만 쓰인 처방전)"""
    await svc.delete_analysis(user, analysis_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@guide_router.post("/{guide_id}/feedback", response_model=GuideFeedbackResponse, status_code=status.HTTP_201_CREATED)
async def post_guide_feedback(guide_id: int, body: GuideFeedbackRequest, user: CurrentUser) -> GuideFeedbackResponse:
    """R-9 — 안내문 피드백 (도움됐어요 1 / 도움이 안 됐어요 -1, 한마디는 선택)"""
    return GuideFeedbackResponse(feedback_id=await svc.save_feedback(user, guide_id, body.rating, body.comment))
