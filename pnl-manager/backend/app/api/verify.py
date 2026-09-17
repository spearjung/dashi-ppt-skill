"""OCR 검증·확정 API(§FR-05)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_session
from ..enums import UploadStatus
from ..models import ConfirmedRecord, Engagement, Upload
from ..ocr.confidence import requires_individual_confirmation
from ..schemas import (
    ConfirmedRecordOut,
    ConfirmIn,
    ConfirmResult,
    DecisionBatch,
    ManualRecordIn,
    OcrRecordOut,
    UploadOut,
    VerificationView,
)
from ..services import issues as issues_service
from ..services import pnl as pnl_service
from ..services import snapshots as snapshot_service
from ..services import verification
from .deps import get_upload

router = APIRouter(tags=["verify"])


def _view(session: Session, upload: Upload) -> VerificationView:
    records = []
    for record in upload.ocr_records:
        out = OcrRecordOut.model_validate(record)
        out.needs_individual_confirmation = requires_individual_confirmation(
            record.item_type, record.confidence
        )
        records.append(out)

    confirmed = [
        ConfirmedRecordOut.model_validate(r.confirmed)
        for r in upload.ocr_records
        if r.confirmed is not None
    ]
    previous = snapshot_service.latest_snapshot(session, upload.engagement_id)
    comparison = None
    if previous is not None:
        baseline = {}
        for value in previous.values:
            key = f"{value.wbs_code or value.wbs_id}|{value.item_type}"
            baseline[key] = (baseline.get(key) or 0) + (value.amount or 0)
        comparison = {
            "snapshot_id": previous.id,
            "as_of_date": previous.as_of_date.isoformat() if previous.as_of_date else None,
            "rows": [
                {
                    "ocr_record_id": r.id,
                    "key": f"{(r.wbs.code if r.wbs else r.wbs_code_raw)}|{r.item_type}",
                    "snapshot_amount": baseline.get(
                        f"{(r.wbs.code if r.wbs else r.wbs_code_raw)}|{r.item_type}"
                    ),
                    "ocr_amount": r.amount,
                    "delta": (
                        None
                        if r.amount is None
                        or baseline.get(f"{(r.wbs.code if r.wbs else r.wbs_code_raw)}|{r.item_type}")
                        is None
                        else r.amount
                        - baseline[f"{(r.wbs.code if r.wbs else r.wbs_code_raw)}|{r.item_type}"]
                    ),
                }
                for r in upload.ocr_records
            ],
        }

    return VerificationView(
        upload=UploadOut.model_validate(upload),
        records=records,
        confirmed=confirmed,
        arithmetic_log=upload.arithmetic_log or [],
        snapshot_comparison=comparison,
        gate=verification.confirmation_gate(upload).as_dict(),
    )


@router.get("/uploads/{upload_id}/verification", response_model=VerificationView)
def get_verification(upload: Upload = Depends(get_upload), session: Session = Depends(get_session)):
    return _view(session, upload)


@router.post("/uploads/{upload_id}/decisions", response_model=VerificationView)
def apply_decisions(
    payload: DecisionBatch,
    upload: Upload = Depends(get_upload),
    session: Session = Depends(get_session),
):
    """값별 액션 6종을 일괄 적용한다."""
    by_id = {r.id: r for r in upload.ocr_records}
    for decision in payload.decisions:
        record = by_id.get(decision.ocr_record_id)
        if record is None:
            raise HTTPException(
                404, f"OcrRecord #{decision.ocr_record_id}는 이 업로드에 속하지 않습니다."
            )
        try:
            verification.apply_decision(
                session,
                record,
                verification.RecordDecision(
                    ocr_record_id=decision.ocr_record_id,
                    action=decision.action.value,
                    amount=decision.amount,
                    quantity=decision.quantity,
                    unit=decision.unit,
                    wbs_id=decision.wbs_id,
                    item_type=decision.item_type.value if decision.item_type else None,
                    value_basis=decision.value_basis.value if decision.value_basis else None,
                    period_from=decision.period_from,
                    period_to=decision.period_to,
                    note=decision.note,
                    change_link_id=decision.change_link_id,
                ),
                payload.actor,
            )
        except verification.VerificationError as exc:
            raise HTTPException(422, str(exc)) from exc

    if upload.status in (UploadStatus.UPLOADED.value, UploadStatus.OCR_DONE.value):
        upload.status = UploadStatus.VERIFYING.value
    session.flush()
    return _view(session, upload)


@router.post("/uploads/{upload_id}/manual-records", response_model=VerificationView)
def add_manual_record(
    payload: ManualRecordIn,
    upload: Upload = Depends(get_upload),
    session: Session = Depends(get_session),
):
    """판독 실패값·미판독값을 직접 입력한다."""
    try:
        verification.add_manual_record(
            session,
            upload=upload,
            item_type=payload.item_type.value,
            wbs_id=payload.wbs_id,
            amount=payload.amount,
            quantity=payload.quantity,
            unit=payload.unit,
            value_basis=payload.value_basis.value,
            period_from=payload.period_from,
            period_to=payload.period_to,
            raw_label=payload.raw_label,
            actor=payload.actor,
        )
    except verification.VerificationError as exc:
        raise HTTPException(422, str(exc)) from exc
    session.flush()
    return _view(session, upload)


@router.post("/uploads/{upload_id}/confirm", response_model=ConfirmResult)
def confirm(
    payload: ConfirmIn,
    upload: Upload = Depends(get_upload),
    session: Session = Depends(get_session),
):
    """Upload 단위 확정 → Snapshot 생성 → 계산·조치사항 갱신(§Step 5)."""
    try:
        verification.confirm_upload(session, upload, actor=payload.actor, force=payload.force)
    except verification.VerificationError as exc:
        raise HTTPException(409, str(exc)) from exc

    engagement = session.get(Engagement, upload.engagement_id)
    previous = snapshot_service.latest_snapshot(session, engagement.id)
    snapshot = None
    diff = None
    if payload.create_snapshot:
        snapshot = snapshot_service.create_snapshot(
            session,
            engagement,
            label=payload.label or f"Upload #{upload.id} 확정",
            actor=payload.actor,
        )
        diff = snapshot_service.diff_snapshots(previous, snapshot)

    created = issues_service.scan_upload(session, upload, actor=payload.actor)
    created += issues_service.refresh_action_items(session, engagement)
    session.flush()

    return ConfirmResult(
        upload=UploadOut.model_validate(upload),
        snapshot_id=snapshot.id if snapshot else None,
        issues_created=len(created),
        diff=diff,
        pnl=pnl_service.compute(session, engagement).as_dict(),
    )


@router.get("/engagements/{engagement_id}/confirmed-records", response_model=list[ConfirmedRecordOut])
def list_confirmed(engagement_id: int, session: Session = Depends(get_session)):
    return list(
        session.execute(
            select(ConfirmedRecord)
            .where(ConfirmedRecord.engagement_id == engagement_id)
            .order_by(ConfirmedRecord.id)
        ).scalars()
    )
