"""Snapshot 관리(§FR-08).

확정 시점마다 Engagement·WBS·항목별 값을 보존하며 기존 Snapshot은
덮어쓰지 않는다. 특정 Snapshot 기준으로 대시보드를 재현할 수 있어야 하므로
계산 결과도 산식 버전과 함께 함께 저장한다(§9 재현성).
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..calc.formulas import FORMULA_VERSION
from ..enums import CALCULABLE_ACTIONS, ItemType
from ..models import ConfirmedRecord, Engagement, Snapshot, SnapshotValue, Upload
from . import audit

#: 연속 Snapshot 간 비교 항목(§FR-08)
DIFF_ITEMS: tuple[str, ...] = (
    ItemType.TIME.value,
    ItemType.EXPENSE.value,
    ItemType.OS.value,
    ItemType.BILLING.value,
    ItemType.WIP.value,
    ItemType.LTD.value,
)


def create_snapshot(
    session: Session,
    engagement: Engagement,
    *,
    upload_ids: list[int] | None = None,
    label: str | None = None,
    as_of_date: date | None = None,
    actor: str | None = None,
) -> Snapshot:
    """현재 확정값 전체를 새 Snapshot으로 보존한다."""
    from .pnl import build_input  # 순환 import 회피

    records = _calculable_records(session, engagement.id)
    resolved_as_of = as_of_date or max(
        (r.as_of_date or r.period_to for r in records if (r.as_of_date or r.period_to)),
        default=None,
    )

    snapshot = Snapshot(
        engagement_id=engagement.id,
        as_of_date=resolved_as_of,
        created_at=datetime.now(),
        upload_ids=upload_ids or _confirmed_upload_ids(session, engagement.id),
        formula_version=FORMULA_VERSION,
        label=label,
    )
    session.add(snapshot)
    session.flush()

    for rec in records:
        snapshot.values.append(
            SnapshotValue(
                wbs_id=rec.wbs_id,
                wbs_code=rec.wbs.code if rec.wbs else None,
                item_type=rec.item_type,
                amount=rec.amount,
                quantity=rec.quantity,
                value_basis=rec.value_basis,
                period_from=rec.period_from,
                period_to=rec.period_to,
                as_of_date=rec.as_of_date,
                confirmed_record_id=rec.id,
            )
        )
    session.flush()

    data = build_input(session, engagement, snapshot=snapshot)
    from ..calc.formulas import compute_pnl

    snapshot.result = compute_pnl(data).as_dict()
    session.flush()

    audit.log(
        session,
        entity="snapshot",
        entity_id=snapshot.id,
        field="created",
        after=f"as_of={resolved_as_of}, values={len(snapshot.values)}",
        actor=actor,
    )
    return snapshot


def _calculable_records(session: Session, engagement_id: int) -> list[ConfirmedRecord]:
    stmt = select(ConfirmedRecord).where(
        ConfirmedRecord.engagement_id == engagement_id,
        ConfirmedRecord.action.in_([a.value for a in CALCULABLE_ACTIONS]),
    )
    return list(session.execute(stmt).scalars())


def _confirmed_upload_ids(session: Session, engagement_id: int) -> list[int]:
    from ..enums import UploadStatus

    stmt = select(Upload.id).where(
        Upload.engagement_id == engagement_id,
        Upload.status == UploadStatus.CONFIRMED.value,
    )
    return [row for row in session.execute(stmt).scalars()]


def latest_snapshot(session: Session, engagement_id: int) -> Snapshot | None:
    stmt = (
        select(Snapshot)
        .where(Snapshot.engagement_id == engagement_id)
        .order_by(Snapshot.created_at.desc(), Snapshot.id.desc())
        .limit(1)
    )
    return session.execute(stmt).scalars().first()


def diff_snapshots(previous: Snapshot | None, current: Snapshot) -> dict:
    """연속 Snapshot 간 증감을 계산한다(§FR-08)."""
    def totals(snapshot: Snapshot | None) -> dict[str, int]:
        out: dict[str, int] = {}
        if snapshot is None:
            return out
        for value in snapshot.values:
            if value.amount is None:
                continue
            out[value.item_type] = out.get(value.item_type, 0) + value.amount
        return out

    prev_totals = totals(previous)
    cur_totals = totals(current)
    items = {
        item: {
            "previous": prev_totals.get(item, 0),
            "current": cur_totals.get(item, 0),
            "delta": cur_totals.get(item, 0) - prev_totals.get(item, 0),
        }
        for item in DIFF_ITEMS
        if item in prev_totals or item in cur_totals
    }

    prev_result = (previous.result or {}) if previous else {}
    cur_result = current.result or {}
    derived_keys = (
        "eac",
        "final_expected_balance",
        "expected_end_wip",
        "ltd_required",
        "remaining_input_estimate",
    )
    derived = {
        key: {
            "previous": prev_result.get(key),
            "current": cur_result.get(key),
            "delta": (
                None
                if prev_result.get(key) is None or cur_result.get(key) is None
                else cur_result[key] - prev_result[key]
            ),
        }
        for key in derived_keys
    }

    # LTD 조정 후 WIP 재발생 여부(§FR-08)
    ltd_prev = prev_totals.get(ItemType.LTD.value, 0)
    ltd_cur = cur_totals.get(ItemType.LTD.value, 0)
    wip_delta = items.get(ItemType.WIP.value, {}).get("delta", 0)
    wip_regrowth = ltd_cur > ltd_prev and wip_delta > 0

    return {
        "previous_snapshot_id": previous.id if previous else None,
        "current_snapshot_id": current.id,
        "previous_as_of": previous.as_of_date.isoformat() if previous and previous.as_of_date else None,
        "current_as_of": current.as_of_date.isoformat() if current.as_of_date else None,
        "items": items,
        "derived": derived,
        "wip_regrowth_after_ltd": wip_regrowth,
    }
