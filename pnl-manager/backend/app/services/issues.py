"""이상징후·조치사항 생성과 해소(§FR-09, §FR-12).

재분류 선택 시 관련 WBS의 예상 LTD·계약 잔액을 즉시 재계산해 전·후 값을
나란히 반환한다(§FR-09).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config
from ..enums import (
    CALCULABLE_ACTIONS,
    IssueSeverity,
    IssueStatus,
    IssueType,
    RecordAction,
)
from ..models import ConfirmedRecord, Contract, Engagement, Issue, OcrRecord, Upload, Wbs
from ..rules.anomalies import (
    ACTION_LABELS,
    EngagementView,
    RecordView,
    WbsView,
    detect_anomalies,
)
from . import audit
from .pnl import compute

#: 값을 바꾸지 않고 선택만 기록하는 조치(§FR-12 조치사항)
DECISION_ONLY_ACTIONS = frozenset(
    {
        "request_change_order",
        "book_ltd",
        "reduce_mm",
        "issue_invoice",
        "check_billing_plan",
        "upload_backlog",
        "enter_manually",
    }
)


def _wbs_views(session: Session, engagement_id: int) -> list[WbsView]:
    rows = session.execute(
        select(Wbs, Contract.seq)
        .join(Contract, Wbs.contract_id == Contract.id)
        .where(Contract.engagement_id == engagement_id)
        .order_by(Contract.seq, Wbs.code)
    ).all()
    return [
        WbsView(
            id=w.id,
            code=w.code,
            contract_seq=seq,
            valid_from=w.valid_from or c_valid_from(session, w),
            valid_to=w.valid_to or c_valid_to(session, w),
        )
        for w, seq in rows
    ]


def c_valid_from(session: Session, wbs: Wbs):
    contract = session.get(Contract, wbs.contract_id)
    return contract.valid_from if contract else None


def c_valid_to(session: Session, wbs: Wbs):
    contract = session.get(Contract, wbs.contract_id)
    return contract.valid_to if contract else None


def scan_upload(session: Session, upload: Upload, *, actor: str | None = None) -> list[Issue]:
    """판독 결과에 대해 이상징후를 탐지하고 Issue로 등록한다."""
    engagement = session.get(Engagement, upload.engagement_id)
    wbs_list = _wbs_views(session, upload.engagement_id)

    baseline: dict[tuple[int | None, str], int] = {}
    for rec in session.execute(
        select(ConfirmedRecord).where(
            ConfirmedRecord.engagement_id == upload.engagement_id,
            ConfirmedRecord.action.in_([a.value for a in CALCULABLE_ACTIONS]),
        )
    ).scalars():
        if rec.amount is None or rec.upload_id == upload.id:
            continue
        key = (rec.wbs_id, rec.item_type)
        baseline[key] = baseline.get(key, 0) + rec.amount

    views = [
        RecordView(
            id=r.id,
            wbs_id=r.wbs_id,
            wbs_code=r.wbs.code if r.wbs else r.wbs_code_raw,
            item_type=r.item_type,
            amount=r.amount,
            unit=r.unit,
            period_from=r.period_from,
            period_to=r.period_to,
            as_of_date=r.as_of_date,
            duplicate_verdict=r.duplicate_verdict,
            arithmetic_passed=None
            if not r.arithmetic_check
            else bool(r.arithmetic_check.get("passed")),
            arithmetic_message=None if not r.arithmetic_check else r.arithmetic_check.get("message"),
        )
        for r in upload.ocr_records
    ]

    anomalies = detect_anomalies(
        engagement=EngagementView(
            id=engagement.id, start_date=engagement.start_date, end_date=engagement.end_date
        ),
        records=views,
        wbs_list=wbs_list,
        baseline_amounts=baseline,
    )

    created: list[Issue] = []
    for anomaly in anomalies:
        existing = session.execute(
            select(Issue).where(
                Issue.engagement_id == engagement.id, Issue.dedup_key == anomaly.dedup_key
            )
        ).scalars().first()
        if existing is not None:
            # 재판독으로 OcrRecord가 새로 생성된 경우 참조를 갱신한다.
            if existing.status == IssueStatus.OPEN.value:
                merged = sorted(
                    set(existing.related_record_ids or []) | set(anomaly.related_record_ids)
                )
                current = {r.id for r in upload.ocr_records}
                existing.related_record_ids = [
                    rid for rid in merged if rid in current
                ] or merged
                existing.detail = anomaly.detail
            continue
        issue = Issue(
            engagement_id=engagement.id,
            type=anomaly.type.value,
            severity=anomaly.severity.value,
            title=anomaly.title,
            detail=anomaly.detail,
            related_record_ids=list(anomaly.related_record_ids),
            related_wbs_id=anomaly.related_wbs_id,
            suggested_actions=[
                {"key": a, "label": ACTION_LABELS.get(a, a)} for a in anomaly.suggested_actions
            ],
            dedup_key=anomaly.dedup_key,
        )
        session.add(issue)
        created.append(issue)
    session.flush()
    if created:
        audit.log(
            session,
            entity="issue",
            entity_id=upload.id,
            field="scan_upload",
            after=f"{len(created)}건 생성",
            actor=actor,
        )
    return created


def preview_reclassification(
    session: Session, issue: Issue, target_wbs_id: int
) -> dict:
    """재분류 전·후의 예상 LTD·계약 잔액을 계산해 나란히 반환한다(§FR-09).

    실제 값을 바꾸지 않고 재계산만 수행한다.
    """
    engagement = session.get(Engagement, issue.engagement_id)
    before = compute(session, engagement).as_dict()

    records = _issue_records(session, issue)
    originals = [(r, r.wbs_id, r.action) for r in records]
    try:
        for record in records:
            record.wbs_id = target_wbs_id
            record.action = RecordAction.REASSIGN.value
        session.flush()
        after = compute(session, engagement).as_dict()
    finally:
        for record, wbs_id, action in originals:
            record.wbs_id = wbs_id
            record.action = action
        session.flush()

    return {
        "issue_id": issue.id,
        "target_wbs_id": target_wbs_id,
        "before": _ltd_summary(before),
        "after": _ltd_summary(after),
    }


def _ltd_summary(pnl: dict) -> dict:
    return {
        "engagement": {
            "ltd_required": pnl["ltd_required"],
            "contract_balance": pnl["contract_balance"],
            "eac": pnl["eac"],
            "final_expected_balance": pnl["final_expected_balance"],
        },
        "wbs": [
            {
                "wbs_id": w["wbs_id"],
                "code": w["code"],
                "contract_seq": w["contract_seq"],
                "cumulative_usage": w["cumulative_usage"],
                "ltd_required": w["ltd_required"],
                "allocated_contract_amount": w["allocated_contract_amount"],
                "balance": w["allocated_contract_amount"] - w["cumulative_usage"],
            }
            for w in pnl["wbs_results"]
        ],
        "contracts": [
            {
                "seq": c["seq"],
                "amount": c["amount"],
                "ltd_required": c["ltd_required"],
                "balance": c["balance"],
            }
            for c in pnl["contracts"]
        ],
    }


def _issue_records(session: Session, issue: Issue) -> list[ConfirmedRecord]:
    """Issue가 가리키는 OcrRecord의 확정 레코드를 찾는다."""
    out: list[ConfirmedRecord] = []
    for ocr_id in issue.related_record_ids or []:
        confirmed = session.execute(
            select(ConfirmedRecord).where(ConfirmedRecord.ocr_record_id == ocr_id)
        ).scalars().first()
        if confirmed is not None:
            out.append(confirmed)
    return out


def resolve_issue(
    session: Session,
    issue: Issue,
    *,
    selected_action: str,
    target_wbs_id: int | None = None,
    actor: str | None = None,
) -> dict:
    """선택한 조치를 적용하고 재계산 결과를 반환한다."""
    engagement = session.get(Engagement, issue.engagement_id)
    before = compute(session, engagement).as_dict()
    records = _issue_records(session, issue)

    if selected_action == "reassign_to_next_wbs":
        if target_wbs_id is None:
            raise ValueError("재분류 대상 WBS(target_wbs_id)를 지정하십시오.")
        for record in records:
            audit.log(
                session,
                entity="confirmed_record",
                entity_id=record.id,
                field="wbs_id",
                before=record.wbs_id,
                after=target_wbs_id,
                actor=actor,
            )
            record.original_wbs_id = record.original_wbs_id or record.wbs_id
            record.wbs_id = target_wbs_id
            record.action = RecordAction.REASSIGN.value
    elif selected_action in ("exclude_temporarily", "exclude"):
        for record in records:
            audit.log(
                session,
                entity="confirmed_record",
                entity_id=record.id,
                field="action",
                before=record.action,
                after=RecordAction.EXCLUDE.value,
                actor=actor,
            )
            record.action = RecordAction.EXCLUDE.value
    elif selected_action in ("keep_current_wbs", "keep", "confirm"):
        pass
    elif selected_action == "check_duplicate_input":
        for record in records:
            record.action = RecordAction.DUPLICATE.value
            record.note = "중복 입력 여부 확인 대상으로 표시되어 계산에서 제외합니다."
    elif selected_action in ("replace",):
        for record in records:
            matched = session.execute(
                select(OcrRecord).where(OcrRecord.id == record.ocr_record_id)
            ).scalars().first()
            prior_id = matched.duplicate_of_record_id if matched else None
            if prior_id:
                prior = session.get(ConfirmedRecord, prior_id)
                if prior is not None:
                    prior.action = RecordAction.EXCLUDE.value
                    prior.note = "최신 Snapshot 값으로 대체되었습니다."
                    record.change_link_id = prior.id
    elif selected_action in ("set_unit", "recheck_source", "edit"):
        # 값 수정은 검증 화면의 액션으로 처리한다. 여기서는 상태만 정리한다.
        pass
    elif selected_action in DECISION_ONLY_ACTIONS:
        # 조치사항(§FR-12)의 선택은 EP의 의사결정 기록이다. 값은 바꾸지 않고
        # 선택 내용과 시점만 감사 로그에 남긴다.
        pass
    else:
        raise ValueError(f"지원하지 않는 조치입니다: {selected_action}")

    issue.selected_action = selected_action
    issue.status = IssueStatus.RESOLVED.value
    issue.resolved_at = datetime.now()
    session.flush()

    after = compute(session, engagement).as_dict()
    audit.log(
        session,
        entity="issue",
        entity_id=issue.id,
        field="selected_action",
        before=None,
        after=selected_action,
        actor=actor,
    )
    return {
        "issue_id": issue.id,
        "selected_action": selected_action,
        "before": _ltd_summary(before),
        "after": _ltd_summary(after),
    }


def refresh_action_items(session: Session, engagement: Engagement) -> list[Issue]:
    """조치사항 자동 등록(§FR-12).

    LTD 필요액 > 0, 미청구액 > 기준치, Backlog 미입력, 이상징후 미해결 시
    Billing·WIP 조치사항으로 등록한다.
    """
    pnl = compute(session, engagement)
    created: list[Issue] = []

    def upsert(
        *, issue_type: IssueType, severity: IssueSeverity, title: str, detail: str, actions: tuple[str, ...], dedup: str
    ) -> None:
        existing = session.execute(
            select(Issue).where(Issue.engagement_id == engagement.id, Issue.dedup_key == dedup)
        ).scalars().first()
        if existing is not None:
            # 수치는 항상 최신으로 갱신한다.
            existing.title = title
            existing.detail = detail
            existing.severity = severity.value
            # 이미 조치를 선택한 건은 다시 열지 않는다. 조치(예: 추가계약 추진)가
            # 반영되기까지 조건은 계속 성립하므로, 재오픈하면 EP의 의사결정 기록이
            # 사라진다. 조건 자체는 대시보드의 '조치 필요 프로젝트'가 별도로 노출한다.
            if (
                existing.status == IssueStatus.RESOLVED.value
                and existing.selected_action is None
            ):
                existing.status = IssueStatus.OPEN.value
                existing.resolved_at = None
            return
        issue = Issue(
            engagement_id=engagement.id,
            type=issue_type.value,
            severity=severity.value,
            title=title,
            detail=detail,
            suggested_actions=[{"key": a, "label": ACTION_LABELS.get(a, a)} for a in actions],
            dedup_key=dedup,
        )
        session.add(issue)
        created.append(issue)

    if pnl.ltd_outstanding > 0:
        upsert(
            issue_type=IssueType.WIP_ACTION,
            severity=IssueSeverity.HIGH,
            title=f"LTD 잔여 상각 필요액 {pnl.ltd_outstanding:,}원 — 상각 또는 추가계약 결정 필요",
            detail=(
                f"종료예상 사용액 {pnl.eac:,}원이 총 계약금액 {pnl.total_contract_amount:,}원을 "
                f"초과합니다(LTD 필요액 {pnl.ltd_required:,}원, 기 조정 {pnl.ltd_adjusted:,}원). "
                "추가계약으로 회수하거나 LTD 상각을 결정하십시오."
            ),
            actions=("request_change_order", "book_ltd", "reduce_mm"),
            dedup="action:ltd_required",
        )
    if pnl.unbilled_amount > config.UNBILLED_THRESHOLD:
        upsert(
            issue_type=IssueType.BILLING_ACTION,
            severity=IssueSeverity.HIGH,
            title=f"미청구액 {pnl.unbilled_amount:,}원이 기준치 초과",
            detail=(
                f"기준치 {config.UNBILLED_THRESHOLD:,}원을 초과하는 미청구액이 있습니다. "
                "Billing 일정을 확인하십시오."
            ),
            actions=("issue_invoice", "check_billing_plan"),
            dedup="action:unbilled",
        )
    if not pnl.backlog_entered:
        upsert(
            issue_type=IssueType.BACKLOG_MISSING,
            severity=IssueSeverity.MEDIUM,
            title="Backlog 미입력 — 종료예상값이 잠정치",
            detail="Backlog·Staffing 화면을 업로드하거나 잔여 MM을 직접 입력하십시오.",
            actions=("upload_backlog", "enter_manually"),
            dedup="action:backlog_missing",
        )
    else:
        stale = session.execute(
            select(Issue).where(
                Issue.engagement_id == engagement.id, Issue.dedup_key == "action:backlog_missing"
            )
        ).scalars().first()
        if stale is not None and stale.status == IssueStatus.OPEN.value:
            stale.status = IssueStatus.RESOLVED.value
            stale.resolved_at = datetime.now()

    session.flush()
    return created


def open_issues(session: Session, engagement_id: int | None = None) -> list[Issue]:
    stmt = select(Issue).where(Issue.status == IssueStatus.OPEN.value)
    if engagement_id is not None:
        stmt = stmt.where(Issue.engagement_id == engagement_id)
    return list(session.execute(stmt.order_by(Issue.severity, Issue.id)).scalars())
