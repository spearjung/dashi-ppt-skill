"""손익·Snapshot·시나리오·이상징후·대시보드 API(§FR-08 ~ §FR-12)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_session
from ..models import Engagement, Issue, Snapshot
from ..schemas import IssueOut, IssueResolveIn, ScenarioIn, SnapshotOut
from ..services import dashboard as dashboard_service
from ..services import issues as issues_service
from ..services import pnl as pnl_service
from ..services import snapshots as snapshot_service
from .deps import current_actor, get_engagement, get_issue, get_snapshot

router = APIRouter(tags=["analytics"])


@router.get("/dashboard")
def get_dashboard(session: Session = Depends(get_session)):
    """EP Portfolio Dashboard(§FR-12)."""
    return dashboard_service.portfolio(session)


@router.get("/engagements/{engagement_id}/counters")
def get_counters(engagement_id: int, session: Session = Depends(get_session)):
    return dashboard_service.counters(session, engagement_id)


@router.get("/engagements/{engagement_id}/pnl")
def get_pnl(
    snapshot_id: int | None = Query(default=None, description="지정 시 해당 Snapshot 시점으로 재현"),
    engagement: Engagement = Depends(get_engagement),
    session: Session = Depends(get_session),
):
    """프로젝트 손익(§FR-10). snapshot_id를 주면 그 시점 값을 재현한다(§9)."""
    snapshot = None
    if snapshot_id is not None:
        snapshot = session.get(Snapshot, snapshot_id)
        if snapshot is None or snapshot.engagement_id != engagement.id:
            raise HTTPException(404, f"Snapshot #{snapshot_id}를 찾을 수 없습니다.")
    return pnl_service.compute(session, engagement, snapshot=snapshot).as_dict()


@router.get("/engagements/{engagement_id}/snapshots", response_model=list[SnapshotOut])
def list_snapshots(engagement_id: int, session: Session = Depends(get_session)):
    return list(
        session.execute(
            select(Snapshot)
            .where(Snapshot.engagement_id == engagement_id)
            .order_by(Snapshot.created_at.desc(), Snapshot.id.desc())
        ).scalars()
    )


@router.post("/engagements/{engagement_id}/snapshots", response_model=SnapshotOut, status_code=201)
def create_snapshot(
    label: str | None = None,
    actor: str | None = None,
    engagement: Engagement = Depends(get_engagement),
    session: Session = Depends(get_session),
):
    return snapshot_service.create_snapshot(session, engagement, label=label, actor=actor)


@router.get("/snapshots/{snapshot_id}")
def get_snapshot_detail(snapshot: Snapshot = Depends(get_snapshot)):
    return {
        "snapshot": SnapshotOut.model_validate(snapshot).model_dump(),
        "values": [
            {
                "wbs_id": v.wbs_id,
                "wbs_code": v.wbs_code,
                "item_type": v.item_type,
                "amount": v.amount,
                "quantity": v.quantity,
                "value_basis": v.value_basis,
                "period_from": v.period_from.isoformat() if v.period_from else None,
                "period_to": v.period_to.isoformat() if v.period_to else None,
            }
            for v in snapshot.values
        ],
        "result": snapshot.result,
    }


@router.get("/snapshots/{snapshot_id}/diff")
def get_snapshot_diff(
    against: int | None = Query(default=None, description="비교 대상 Snapshot. 기본은 직전 Snapshot"),
    snapshot: Snapshot = Depends(get_snapshot),
    session: Session = Depends(get_session),
):
    """연속 Snapshot 간 증감(§FR-08)."""
    if against is not None:
        previous = session.get(Snapshot, against)
    else:
        previous = session.execute(
            select(Snapshot)
            .where(
                Snapshot.engagement_id == snapshot.engagement_id,
                Snapshot.id < snapshot.id,
            )
            .order_by(Snapshot.id.desc())
            .limit(1)
        ).scalars().first()
    return snapshot_service.diff_snapshots(previous, snapshot)


@router.get("/engagements/{engagement_id}/scenarios")
def get_scenarios(
    engagement: Engagement = Depends(get_engagement), session: Session = Depends(get_session)
):
    """Base·Best·Worst 동시 계산(§FR-11)."""
    return pnl_service.scenarios(session, engagement)


@router.post("/engagements/{engagement_id}/scenarios")
def save_scenario(
    payload: ScenarioIn,
    engagement: Engagement = Depends(get_engagement),
    session: Session = Depends(get_session),
):
    scenario = pnl_service.save_scenario(
        session,
        engagement,
        payload.kind.value,
        payload.model_dump(exclude={"kind"}),
    )
    return {"kind": scenario.kind, "params": scenario.params, "result": scenario.result}


@router.post("/engagements/{engagement_id}/scenarios/preview")
def preview_scenarios(
    payload: list[ScenarioIn],
    engagement: Engagement = Depends(get_engagement),
    session: Session = Depends(get_session),
):
    """변수 변경 즉시 재계산(저장하지 않음)."""
    overrides = {p.kind.value: p.model_dump(exclude={"kind"}) for p in payload}
    return pnl_service.scenarios(session, engagement, overrides=overrides)


@router.get("/engagements/{engagement_id}/issues", response_model=list[IssueOut])
def list_issues(
    engagement_id: int, status: str | None = None, session: Session = Depends(get_session)
):
    stmt = select(Issue).where(Issue.engagement_id == engagement_id)
    if status:
        stmt = stmt.where(Issue.status == status)
    return list(session.execute(stmt.order_by(Issue.id)).scalars())


@router.get("/issues/{issue_id}/reclassification-preview")
def preview_reclassification(
    target_wbs_id: int = Query(...),
    issue: Issue = Depends(get_issue),
    session: Session = Depends(get_session),
):
    """재분류 전·후 예상 LTD·계약 잔액을 나란히 반환한다(§FR-09)."""
    return issues_service.preview_reclassification(session, issue, target_wbs_id)


@router.post("/issues/{issue_id}/resolve")
def resolve_issue(
    payload: IssueResolveIn,
    issue: Issue = Depends(get_issue),
    session: Session = Depends(get_session),
    session_actor: str | None = Depends(current_actor),
):
    actor = session_actor or payload.actor
    try:
        result = issues_service.resolve_issue(
            session,
            issue,
            selected_action=payload.selected_action,
            target_wbs_id=payload.target_wbs_id,
            actor=actor,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    engagement = session.get(Engagement, issue.engagement_id)
    snapshot = snapshot_service.create_snapshot(
        session,
        engagement,
        label=f"Issue #{issue.id} 조치: {payload.selected_action}",
        actor=actor,
    )
    issues_service.refresh_action_items(session, engagement)
    result["snapshot_id"] = snapshot.id
    return result


@router.post("/engagements/{engagement_id}/action-items")
def refresh_action_items(
    engagement: Engagement = Depends(get_engagement), session: Session = Depends(get_session)
):
    created = issues_service.refresh_action_items(session, engagement)
    return {"created": len(created)}
