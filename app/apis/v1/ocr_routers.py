"""피처 1 OCR — O-1 ~ O-5 (API 명세서 3장)"""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, Query, UploadFile
from starlette import status
from starlette.responses import Response

from app.dependencies.security import get_request_user
from app.dtos.ocr import (
    DrugSearchResponse,
    ItemPatchRequest,
    JobCreatedResponse,
    JobResponse,
    PrescriptionResponse,
)
from app.models.users import User
from app.services import prescriptions as svc

ocr_router = APIRouter(tags=["ocr"])
CurrentUser = Annotated[User, Depends(get_request_user)]


@ocr_router.post("/prescriptions", response_model=JobCreatedResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_prescriptions(
    background: BackgroundTasks,
    user: CurrentUser,
    files: Annotated[list[UploadFile], File(description="사진 최대 5장 · 1장 10MB 이하 · JPG / PNG / PDF")],
) -> JobCreatedResponse:
    """O-1 — 파일 검사만 바로 하고 OCR은 작업으로 돌림 (결과는 O-5)"""
    raw = [(f.filename or "", await f.read(svc.MAX_BYTES + 1)) for f in files[: svc.MAX_FILES + 1]]
    blobs = svc.validate_uploads(raw)
    job = await svc.create_job(user, blobs)
    background.add_task(
        svc.process_job, job.id, user.id, blobs
    )  # 사진 저장 · OCR 모두 응답 뒤에 (S3가 느려도 응답은 바로)
    return JobCreatedResponse(job_id=job.id, status="queued")


@ocr_router.get("/ocr-jobs/{job_id}", response_model=JobResponse)
async def get_ocr_job(job_id: int, user: CurrentUser) -> JobResponse:
    """O-5 — 1초 간격 폴링"""
    return JobResponse.model_validate(await svc.get_job(user, job_id))


@ocr_router.get("/prescriptions/{prescription_id}", response_model=PrescriptionResponse)
async def get_prescription(prescription_id: int, user: CurrentUser) -> PrescriptionResponse:
    """O-2 — 인식 결과 (피처 2가 받는 입력 형식)"""
    return PrescriptionResponse.model_validate(await svc.get_prescription(user, prescription_id))


@ocr_router.patch("/prescriptions/{prescription_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def patch_prescription_item(
    prescription_id: int, item_id: int, body: ItemPatchRequest, user: CurrentUser
) -> Response:
    """O-3 — 약 고르기 · 빼기 · 숫자 고치기"""
    await svc.patch_item(user, prescription_id, item_id, body)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@ocr_router.get("/drugs/search", response_model=DrugSearchResponse)
async def search_drugs(
    user: CurrentUser,
    q: Annotated[str, Query(min_length=1, max_length=100)],
    size: Annotated[int, Query(ge=1, le=20)] = 5,
) -> DrugSearchResponse:
    """O-4 — 약 이름 검색 (오타 · 띄어쓰기 · mg/밀리그람 섞여도 됨)"""
    return DrugSearchResponse.model_validate(await svc.search_drugs(q, size))
