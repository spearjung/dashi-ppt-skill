"""EP Portfolio Dashboard(§FR-12, §7)."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..enums import (
    CALCULABLE_ACTIONS,
    Confidence,
    DuplicateVerdict,
    IssueStatus,
    IssueType,
    UploadStatus,
)
from ..models import ConfirmedRecord, Engagement, Issue, OcrRecord, Upload
from .pnl import compute
from .snapshots import latest_snapshot


def counters(session: Session, engagement_id: int | None = None) -> dict:
    """처리 대기 카운터. 카운터 클릭 시 이동할 검증 대기열의 필터 키를 함께 준다."""

    def _scope(stmt, model=Upload):
        if engagement_id is not None:
            return stmt.where(model.engagement_id == engagement_id)
        return stmt

    pending_uploads = session.execute(
        _scope(
            select(func.count(Upload.id)).where(
                Upload.status.in_(
                    [UploadStatus.UPLOADED.value, UploadStatus.OCR_DONE.value, UploadStatus.VERIFYING.value]
                )
            )
        )
    ).scalar_one()

    unconfirmed_records = session.execute(
        _scope(
            select(func.count(OcrRecord.id))
            .join(Upload, OcrRecord.upload_id == Upload.id)
            .outerjoin(ConfirmedRecord, ConfirmedRecord.ocr_record_id == OcrRecord.id)
            .where(
                Upload.status != UploadStatus.CONFIRMED.value,
                ConfirmedRecord.id.is_(None),
            )
        )
    ).scalar_one()

    read_failures = session.execute(
        _scope(
            select(func.count(OcrRecord.id))
            .join(Upload, OcrRecord.upload_id == Upload.id)
            .where(
                OcrRecord.confidence.in_([Confidence.FAILED.value, Confidence.LOW.value]),
                Upload.status != UploadStatus.CONFIRMED.value,
            )
        )
    ).scalar_one()

    duplicate_suspects = session.execute(
        _scope(
            select(func.count(OcrRecord.id))
            .join(Upload, OcrRecord.upload_id == Upload.id)
            .where(
                OcrRecord.duplicate_verdict.in_(
                    [
                        DuplicateVerdict.EXACT_DUPLICATE.value,
                        DuplicateVerdict.LATEST_SNAPSHOT_CANDIDATE.value,
                    ]
                )
            )
        )
    ).scalar_one()

    wbs_review = session.execute(
        _scope(
            select(func.count(Issue.id)).where(
                Issue.type == IssueType.WBS_ATTRIBUTION.value,
                Issue.status == IssueStatus.OPEN.value,
            ),
            Issue,
        )
    ).scalar_one()

    return {
        "pending_uploads": pending_uploads,
        "unconfirmed_ocr_records": unconfirmed_records,
        "read_failures": read_failures,
        "duplicate_suspects": duplicate_suspects,
        "wbs_attribution_review": wbs_review,
    }


def portfolio(session: Session) -> dict:
    """프로젝트별 최종 예상손익과 조치 필요 프로젝트를 집계한다."""
    engagements = list(session.execute(select(Engagement).order_by(Engagement.id)).scalars())
    rows: list[dict] = []
    action_required: list[dict] = []

    for engagement in engagements:
        pnl = compute(session, engagement)
        snapshot = latest_snapshot(session, engagement.id)
        issues = list(
            session.execute(
                select(Issue).where(
                    Issue.engagement_id == engagement.id,
                    Issue.status == IssueStatus.OPEN.value,
                )
            ).scalars()
        )
        row = {
            "engagement_id": engagement.id,
            "name": engagement.name,
            "client": engagement.client,
            "engagement_code": engagement.engagement_code,
            "ep": engagement.ep,
            "em": engagement.em,
            "contract_type": engagement.contract_type,
            "total_contract_amount": pnl.total_contract_amount,
            "cumulative_usage": pnl.cumulative_usage,
            "remaining_input_estimate": pnl.remaining_input_estimate,
            "eac": pnl.eac,
            "final_expected_balance": pnl.final_expected_balance,
            "expected_margin_rate": pnl.expected_margin_rate,
            "expected_end_wip": pnl.expected_end_wip,
            "ltd_required": pnl.ltd_required,
            "ltd_outstanding": pnl.ltd_outstanding,
            "unbilled_amount": pnl.unbilled_amount,
            "provisional": pnl.provisional,
            "backlog_entered": pnl.backlog_entered,
            "latest_snapshot_id": snapshot.id if snapshot else None,
            "latest_snapshot_as_of": (
                snapshot.as_of_date.isoformat() if snapshot and snapshot.as_of_date else None
            ),
            "open_issue_count": len(issues),
            "warnings": pnl.warnings,
        }
        rows.append(row)
        if issues or pnl.ltd_outstanding > 0 or pnl.final_expected_balance < 0:
            action_required.append(
                {
                    "engagement_id": engagement.id,
                    "name": engagement.name,
                    "reasons": _reasons(pnl, issues),
                    "severity": "high"
                    if pnl.ltd_outstanding > 0 or pnl.final_expected_balance < 0
                    else "medium",
                }
            )

    return {
        "counters": counters(session),
        "projects": rows,
        "action_required": action_required,
        "latest_snapshot_as_of": max(
            (r["latest_snapshot_as_of"] for r in rows if r["latest_snapshot_as_of"]),
            default=None,
        ),
    }


def _reasons(pnl, issues: list[Issue]) -> list[str]:
    reasons: list[str] = []
    if pnl.ltd_outstanding > 0:
        reasons.append(f"LTD 필요액 {pnl.ltd_outstanding:,}원")
    if pnl.final_expected_balance < 0:
        reasons.append(f"최종 예상 잔액 {pnl.final_expected_balance:,}원(손실 예상)")
    if not pnl.backlog_entered:
        reasons.append("Backlog 미입력")
    for issue in issues:
        reasons.append(issue.title)
    return reasons
