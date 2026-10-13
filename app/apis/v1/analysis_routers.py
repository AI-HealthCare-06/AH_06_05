"""피처 2 RAG 분석 — R-1 ~ R-6 (API 명세서 4장)"""

from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends
from starlette import status

from app.dependencies.security import get_request_user
from app.dtos.analysis import AnalysisCreatedResponse, AnalysisCreateRequest, DiseasesRequest
from app.models.users import User
from app.services import analyses as svc

analysis_router = APIRouter(prefix="/analyses", tags=["analysis"])
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
