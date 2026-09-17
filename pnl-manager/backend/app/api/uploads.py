"""캡처 업로드·판독 API(§FR-02, §FR-03)."""

from __future__ import annotations

from pathlib import Path as FsPath

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_session
from ..enums import ScreenType
from ..models import Engagement, Upload
from ..ocr.pipeline import ingest_payload, run_ocr
from ..ocr.providers import OcrProviderError
from ..ocr.schema import OcrPayload
from ..schemas import OcrPayloadIn, ScreenTypeUpdate, UploadOut, UploadResult
from ..services import issues as issues_service
from ..services import uploads as upload_service
from .deps import current_actor, get_engagement, get_upload

router = APIRouter(tags=["uploads"])


@router.post("/engagements/{engagement_id}/uploads", response_model=list[UploadResult], status_code=201)
async def upload_captures(
    files: list[UploadFile] = File(...),
    screen_type: str | None = Form(default=None),
    uploaded_by: str | None = Form(default=None),
    engagement: Engagement = Depends(get_engagement),
    session: Session = Depends(get_session),
    actor: str | None = Depends(current_actor),
):
    """여러 장을 동시에 업로드한다. 동일 해시는 기존 Upload로 연결하고 경고한다."""
    results: list[UploadResult] = []
    for file in files:
        content = await file.read()
        try:
            upload, duplicate = upload_service.store_upload(
                session,
                engagement=engagement,
                filename=file.filename or "capture.png",
                content=content,
                screen_type=screen_type,
                uploaded_by=actor or uploaded_by,
            )
        except upload_service.UploadError as exc:
            raise HTTPException(400, str(exc)) from exc
        session.flush()
        results.append(
            UploadResult(
                upload=UploadOut.model_validate(upload),
                duplicate=duplicate,
                message=(upload.warnings or [None])[-1] if duplicate else None,
            )
        )
    return results


@router.get("/engagements/{engagement_id}/uploads", response_model=list[UploadOut])
def list_uploads(engagement_id: int, status: str | None = None, session: Session = Depends(get_session)):
    stmt = select(Upload).where(Upload.engagement_id == engagement_id)
    if status:
        stmt = stmt.where(Upload.status == status)
    return list(session.execute(stmt.order_by(Upload.uploaded_at.desc(), Upload.id.desc())).scalars())


@router.get("/uploads/{upload_id}", response_model=UploadOut)
def get_upload_detail(upload: Upload = Depends(get_upload)):
    return upload


@router.get("/uploads/{upload_id}/image")
def get_upload_image(upload: Upload = Depends(get_upload)):
    """검증 화면 좌측 원본 캡처(§7)."""
    path = FsPath(upload.file_path)
    if not path.exists():
        raise HTTPException(404, "원본 캡처 파일을 찾을 수 없습니다.")
    return FileResponse(path)


@router.patch("/uploads/{upload_id}/screen-type", response_model=UploadOut)
def set_screen_type(
    payload: ScreenTypeUpdate,
    upload: Upload = Depends(get_upload),
    session: Session = Depends(get_session),
):
    """자동 분류 결과를 사용자가 확인·변경한다(§FR-02)."""
    return upload_service.set_screen_type(session, upload, payload.screen_type.value)


@router.post("/uploads/{upload_id}/ocr", response_model=UploadOut)
def trigger_ocr(
    provider: str | None = None,
    upload: Upload = Depends(get_upload),
    session: Session = Depends(get_session),
):
    """판독을 실행하고 이상징후를 탐지한다."""
    try:
        run_ocr(session, upload, provider_name=provider)
    except OcrProviderError as exc:
        raise HTTPException(502, str(exc)) from exc
    except ValueError as exc:  # 알 수 없는 엔진 이름 등
        raise HTTPException(400, str(exc)) from exc
    issues_service.scan_upload(session, upload)
    session.flush()
    return upload


@router.post("/uploads/{upload_id}/ocr-payload", response_model=UploadOut)
def inject_payload(
    payload: OcrPayloadIn,
    upload: Upload = Depends(get_upload),
    session: Session = Depends(get_session),
):
    """판독 결과 JSON을 직접 주입한다(오프라인·수기 판독, §9 가용성)."""
    try:
        parsed = OcrPayload.model_validate(payload.payload)
    except Exception as exc:
        raise HTTPException(422, f"OCR 스키마 위반: {exc}") from exc
    ingest_payload(session, upload, parsed)
    issues_service.scan_upload(session, upload)
    session.flush()
    return upload


@router.get("/screen-types")
def list_screen_types():
    return [{"value": s.value, "label": s.value} for s in ScreenType]
