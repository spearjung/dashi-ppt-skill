"""손익 계산 입력 조립(§FR-10).

확정값(ConfirmedRecord) 또는 Snapshot 값만을 입력으로 사용하며
OCR 임시값은 배제한다.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..calc.formulas import (
    BillingInput,
    ContractInput,
    CostRecord,
    EngagementPnl,
    LtdInput,
    PnlInput,
    StaffingInput,
    WbsInput,
    compute_pnl,
)
from ..calc.scenario import ScenarioParams, compute_scenario, compute_scenarios
from ..enums import CALCULABLE_ACTIONS, ScenarioKind
from ..models import (
    BillingPlan,
    ConfirmedRecord,
    Contract,
    Engagement,
    LtdAdjustment,
    Scenario,
    Snapshot,
    StaffingPlan,
    Wbs,
)


def build_input(
    session: Session, engagement: Engagement, *, snapshot: Snapshot | None = None
) -> PnlInput:
    """계산 입력을 조립한다. snapshot을 주면 그 시점 값으로 재현한다(§9 재현성)."""
    contracts = [
        ContractInput(
            id=c.id, seq=c.seq, amount=int(c.amount or 0), valid_from=c.valid_from, valid_to=c.valid_to
        )
        for c in sorted(engagement.contracts, key=lambda c: c.seq)
    ]
    wbs_rows = list(
        session.execute(
            select(Wbs)
            .join(Contract, Wbs.contract_id == Contract.id)
            .where(Contract.engagement_id == engagement.id)
            .order_by(Contract.seq, Wbs.code)
        ).scalars()
    )
    seq_by_contract = {c.id: c.seq for c in contracts}
    wbs_list = [
        WbsInput(
            id=w.id,
            code=w.code,
            contract_id=w.contract_id,
            contract_seq=seq_by_contract.get(w.contract_id, 0),
            valid_from=w.valid_from,
            valid_to=w.valid_to,
        )
        for w in wbs_rows
    ]
    wbs_ids = {w.id for w in wbs_rows}

    if snapshot is not None:
        records = [
            CostRecord(
                wbs_id=v.wbs_id,
                item_type=v.item_type,
                amount=v.amount,
                quantity=v.quantity,
                value_basis=v.value_basis,
                period_from=v.period_from,
                period_to=v.period_to,
                as_of_date=v.as_of_date or snapshot.as_of_date,
            )
            for v in snapshot.values
        ]
    else:
        confirmed = session.execute(
            select(ConfirmedRecord).where(
                ConfirmedRecord.engagement_id == engagement.id,
                ConfirmedRecord.action.in_([a.value for a in CALCULABLE_ACTIONS]),
            )
        ).scalars()
        records = [
            CostRecord(
                wbs_id=c.wbs_id,
                item_type=c.item_type,
                amount=c.amount,
                quantity=c.quantity,
                value_basis=c.value_basis,
                period_from=c.period_from,
                period_to=c.period_to,
                as_of_date=c.as_of_date,
                confirmed_at=c.confirmed_at.date() if c.confirmed_at else None,
            )
            for c in confirmed
        ]

    staffing = [
        StaffingInput(
            wbs_id=p.wbs_id,
            remaining_mm=float(p.remaining_mm or 0.0),
            rate=int(p.rate or 0),
            expected_time=p.expected_time,
            month=p.month,
        )
        for p in session.execute(
            select(StaffingPlan).where(StaffingPlan.wbs_id.in_(wbs_ids or {0}))
        ).scalars()
    ]
    billing = [
        BillingInput(
            wbs_id=p.wbs_id,
            planned_amount=int(p.planned_amount or 0),
            billed_amount=int(p.billed_amount or 0),
            unbilled_amount=p.unbilled_amount,
            billable_expense=int(p.billable_expense or 0),
        )
        for p in session.execute(
            select(BillingPlan).where(BillingPlan.wbs_id.in_(wbs_ids or {0}))
        ).scalars()
    ]
    ltd = [
        LtdInput(wbs_id=a.wbs_id, amount=int(a.amount or 0))
        for a in session.execute(
            select(LtdAdjustment).where(LtdAdjustment.wbs_id.in_(wbs_ids or {0}))
        ).scalars()
    ]

    return PnlInput(
        engagement_id=engagement.id,
        contract_type=engagement.contract_type,
        contracts=contracts,
        wbs_list=wbs_list,
        records=records,
        staffing=staffing,
        billing=billing,
        ltd_adjustments=ltd,
        snapshot_id=snapshot.id if snapshot else None,
        as_of_date=snapshot.as_of_date if snapshot else None,
    )


def compute(session: Session, engagement: Engagement, *, snapshot: Snapshot | None = None) -> EngagementPnl:
    return compute_pnl(build_input(session, engagement, snapshot=snapshot))


def scenarios(
    session: Session, engagement: Engagement, *, overrides: dict[str, dict] | None = None
) -> list[dict]:
    """저장된 시나리오 변수를 적용해 Base·Best·Worst를 계산한다."""
    data = build_input(session, engagement)
    stored = {
        s.kind: ScenarioParams.from_dict(s.params)
        for s in session.execute(
            select(Scenario).where(Scenario.engagement_id == engagement.id)
        ).scalars()
    }
    if overrides:
        for kind, params in overrides.items():
            stored[kind] = ScenarioParams.from_dict(params)
    params_by_kind = {
        kind: stored.get(kind)
        for kind in (ScenarioKind.BASE.value, ScenarioKind.BEST.value, ScenarioKind.WORST.value)
        if stored.get(kind) is not None
    }
    return [r.as_dict() for r in compute_scenarios(data, params_by_kind or None)]


def save_scenario(
    session: Session, engagement: Engagement, kind: str, params: dict
) -> Scenario:
    existing = session.execute(
        select(Scenario).where(Scenario.engagement_id == engagement.id, Scenario.kind == kind)
    ).scalars().first()
    resolved = ScenarioParams.from_dict(params)
    result = compute_scenario(build_input(session, engagement), kind, resolved)
    if existing is None:
        existing = Scenario(engagement_id=engagement.id, kind=kind)
        session.add(existing)
    existing.params = resolved.as_dict()
    existing.result = result.as_dict()
    session.flush()
    return existing
