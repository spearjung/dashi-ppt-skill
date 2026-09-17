"""검증·확정(§FR-05).

값별 액션 6종(확인·수정·제외·다른 WBS로 재분류·중복 표시·판독 실패 표시)을
OcrRecord에 적용해 ConfirmedRecord(확정 데이터)를 만든다.

확정 차단 규칙
  - 고영향 필드가 하나라도 미확인이면 차단(§FR-04, §FR-05)
  - Low·Failed 신뢰도 필드가 남아 있으면 차단(수정 또는 제외 필요)
  - 제외·중복 처리된 행은 차단 대상에서 빠지며 부분 확정을 허용한다
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..enums import (
    CALCULABLE_ACTIONS,
    Confidence,
    DuplicateVerdict,
    ItemType,
    NON_CURRENCY_ITEM_TYPES,
    RecordAction,
    ScreenType,
    UploadStatus,
    ValueBasis,
)
from ..models import (
    BillingPlan,
    ConfirmedRecord,
    Engagement,
    LtdAdjustment,
    OcrRecord,
    StaffingPlan,
    Upload,
    Wbs,
)
from ..ocr.confidence import blocks_confirmation, is_high_impact
from ..ocr.units import normalize_amount
from . import audit

_NON_CURRENCY = {i.value for i in NON_CURRENCY_ITEM_TYPES}


class VerificationError(ValueError):
    pass


@dataclass(slots=True)
class RecordDecision:
    """검증 화면에서 내려온 값별 결정."""

    ocr_record_id: int
    action: str
    amount: int | float | str | None = None
    quantity: float | None = None
    unit: str | None = None
    wbs_id: int | None = None
    item_type: str | None = None
    value_basis: str | None = None
    period_from: str | None = None
    period_to: str | None = None
    note: str | None = None
    change_link_id: int | None = None


def apply_decision(
    session: Session, record: OcrRecord, decision: RecordDecision, actor: str | None
) -> ConfirmedRecord:
    """단일 OcrRecord에 액션을 적용해 ConfirmedRecord를 생성·갱신한다."""
    action = RecordAction(decision.action)
    upload = record.upload
    engagement_id = upload.engagement_id

    confirmed = record.confirmed
    if confirmed is None:
        # 관계가 이미 None으로 적재돼 있을 수 있어 DB를 한 번 더 확인한다.
        confirmed = session.execute(
            select(ConfirmedRecord).where(ConfirmedRecord.ocr_record_id == record.id)
        ).scalars().first()
    if confirmed is None:
        confirmed = ConfirmedRecord(
            ocr_record_id=record.id,
            engagement_id=engagement_id,
            upload_id=upload.id,
        )
    # 관계를 통해 연결해 OcrRecord.confirmed가 즉시 최신 상태가 되게 한다.
    record.confirmed = confirmed
    before = {
        "action": confirmed.action,
        "amount": confirmed.amount,
        "wbs_id": confirmed.wbs_id,
    }

    confirmed.engagement_id = engagement_id
    confirmed.upload_id = upload.id
    confirmed.item_type = decision.item_type or record.item_type
    confirmed.original_amount = record.amount
    confirmed.original_wbs_id = record.wbs_id
    confirmed.as_of_date = record.as_of_date
    confirmed.period_from = _parse_date(decision.period_from) or record.period_from
    confirmed.period_to = _parse_date(decision.period_to) or record.period_to
    confirmed.value_basis = decision.value_basis or record.value_basis
    confirmed.unit = decision.unit or record.unit
    confirmed.note = decision.note
    confirmed.change_link_id = decision.change_link_id
    confirmed.confirmed_by = actor
    confirmed.confirmed_at = datetime.now()
    confirmed.action = action.value
    confirmed.wbs_id = decision.wbs_id if decision.wbs_id is not None else record.wbs_id

    if action is RecordAction.EXCLUDE:
        confirmed.amount = None
        confirmed.quantity = None
    elif action is RecordAction.DUPLICATE:
        confirmed.amount = None
        confirmed.quantity = None
        confirmed.note = decision.note or "중복으로 표시되어 계산에서 제외합니다."
    elif action is RecordAction.FAILED:
        raise VerificationError(
            f"레코드 #{record.id}: 판독 실패로 표시된 값은 직접 입력해야 확정할 수 있습니다."
        )
    else:
        amount, quantity = _resolve_value(record, decision)
        confirmed.amount = amount
        confirmed.quantity = quantity
        if action is RecordAction.REASSIGN and decision.wbs_id is None:
            raise VerificationError(f"레코드 #{record.id}: 재분류 대상 WBS를 지정해야 합니다.")

    session.flush()

    audit.log(
        session,
        entity="confirmed_record",
        entity_id=confirmed.id,
        field="decision",
        before=before,
        after={
            "action": confirmed.action,
            "amount": confirmed.amount,
            "wbs_id": confirmed.wbs_id,
        },
        actor=actor,
    )
    return confirmed


def _resolve_value(
    record: OcrRecord, decision: RecordDecision
) -> tuple[int | None, float | None]:
    item_type = decision.item_type or record.item_type
    if item_type in _NON_CURRENCY:
        quantity = decision.quantity
        if quantity is None and decision.amount is not None:
            quantity = float(decision.amount)
        return None, quantity if quantity is not None else record.quantity

    if decision.amount is None:
        if record.amount is None:
            raise VerificationError(
                f"레코드 #{record.id}: 판독값이 없어 금액을 직접 입력해야 합니다."
            )
        return record.amount, decision.quantity if decision.quantity is not None else record.quantity

    unit = decision.unit or record.unit or "KRW"
    if isinstance(decision.amount, (int, float)) and decision.unit is None:
        # 사용자가 검증 화면에서 원 단위 정수로 직접 입력한 경우
        return int(decision.amount), decision.quantity
    return normalize_amount(decision.amount, unit), decision.quantity


def _parse_date(value: str | None):
    if not value:
        return None
    from datetime import date

    return date.fromisoformat(value)


@dataclass(slots=True)
class GateResult:
    can_confirm: bool
    blockers: list[str]
    unconfirmed_high_impact: list[int]
    unresolved_low: list[int]

    def as_dict(self) -> dict:
        return {
            "can_confirm": self.can_confirm,
            "blockers": self.blockers,
            "unconfirmed_high_impact": self.unconfirmed_high_impact,
            "unresolved_low": self.unresolved_low,
        }


def confirmation_gate(upload: Upload) -> GateResult:
    """최종 확정 가능 여부를 판정한다(§FR-05)."""
    blockers: list[str] = []
    unconfirmed: list[int] = []
    unresolved: list[int] = []

    for record in upload.ocr_records:
        confirmed = record.confirmed
        decided = confirmed is not None
        resolved_out = decided and confirmed.action in (
            RecordAction.EXCLUDE.value,
            RecordAction.DUPLICATE.value,
        )
        if is_high_impact(record.item_type) and not decided:
            unconfirmed.append(record.id)
        if blocks_confirmation(record.confidence) and not resolved_out and not (
            decided and confirmed.action in (RecordAction.EDIT.value, RecordAction.REASSIGN.value)
        ):
            unresolved.append(record.id)
        if record.confidence == Confidence.MEDIUM.value and not decided:
            unconfirmed.append(record.id)

    if unconfirmed:
        blockers.append(
            f"개별 확인이 필요한 필드 {len(set(unconfirmed))}건이 미확인 상태입니다"
            "(고영향 필드·Medium 이하 신뢰도)."
        )
    if unresolved:
        blockers.append(
            f"Low·Failed 신뢰도 필드 {len(set(unresolved))}건이 수정·제외되지 않았습니다."
        )
    if not upload.ocr_records:
        blockers.append("확정할 레코드가 없습니다.")

    return GateResult(
        can_confirm=not blockers,
        blockers=blockers,
        unconfirmed_high_impact=sorted(set(unconfirmed)),
        unresolved_low=sorted(set(unresolved)),
    )


def confirm_upload(
    session: Session, upload: Upload, *, actor: str | None = None, force: bool = False
) -> Upload:
    """Upload 단위 확정. 게이트를 통과하지 못하면 예외를 발생시킨다."""
    gate = confirmation_gate(upload)
    if not gate.can_confirm and not force:
        raise VerificationError(" / ".join(gate.blockers))

    upload.status = UploadStatus.CONFIRMED.value
    upload.confirmed_at = datetime.now()
    upload.confirmed_by = actor
    session.flush()
    _materialize_plans(session, upload)
    audit.log(
        session,
        entity="upload",
        entity_id=upload.id,
        field="status",
        before=UploadStatus.VERIFYING.value,
        after=UploadStatus.CONFIRMED.value,
        actor=actor,
    )
    return upload


def _materialize_plans(session: Session, upload: Upload) -> None:
    """Backlog·Billing·LTD 화면의 확정값을 계획 엔티티로 반영한다.

    같은 Upload에서 이미 생성된 계획은 재확정 시 교체한다.
    """
    for model in (StaffingPlan, BillingPlan, LtdAdjustment):
        for old in session.execute(
            select(model).where(model.source_upload_id == upload.id)
        ).scalars():
            session.delete(old)
    session.flush()

    confirmed = [
        c
        for r in upload.ocr_records
        if (c := r.confirmed) is not None and c.action in {a.value for a in CALCULABLE_ACTIONS}
    ]
    by_row: dict[int, list[ConfirmedRecord]] = {}
    for c in confirmed:
        row = c.ocr_record.row_index if c.ocr_record else 0
        by_row.setdefault(row, []).append(c)

    for row_records in by_row.values():
        wbs_id = next((c.wbs_id for c in row_records if c.wbs_id), None)
        if wbs_id is None:
            continue
        source = next((c.ocr_record for c in row_records if c.ocr_record), None)

        backlog = next(
            (c for c in row_records if c.item_type == ItemType.BACKLOG_MM.value), None
        )
        rate = next((c for c in row_records if c.item_type == ItemType.RATE.value), None)
        if backlog is not None:
            session.add(
                StaffingPlan(
                    wbs_id=wbs_id,
                    person_or_grade=getattr(source, "raw_label", None),
                    month=None,
                    remaining_mm=float(backlog.quantity or 0.0),
                    rate=int(rate.amount or 0) if rate else 0,
                    source_upload_id=upload.id,
                )
            )

        billing = next((c for c in row_records if c.item_type == ItemType.BILLING.value), None)
        if billing is not None and upload.screen_type == ScreenType.BILLING.value:
            session.add(
                BillingPlan(
                    wbs_id=wbs_id,
                    planned_amount=int(billing.amount or 0),
                    billed_amount=int(billing.amount or 0),
                    billing_date=billing.as_of_date,
                    source_upload_id=upload.id,
                )
            )

        ltd = next((c for c in row_records if c.item_type == ItemType.LTD.value), None)
        if ltd is not None:
            session.add(
                LtdAdjustment(
                    wbs_id=wbs_id,
                    adjust_date=ltd.as_of_date,
                    amount=int(ltd.amount or 0),
                    note=ltd.note,
                    source_upload_id=upload.id,
                )
            )
    session.flush()


def add_manual_record(
    session: Session,
    *,
    upload: Upload,
    item_type: str,
    wbs_id: int | None,
    amount: int | None = None,
    quantity: float | None = None,
    unit: str | None = "KRW",
    value_basis: str = ValueBasis.PERIOD.value,
    period_from: str | None = None,
    period_to: str | None = None,
    raw_label: str | None = None,
    actor: str | None = None,
) -> ConfirmedRecord:
    """판독 실패·미판독 값을 직접 입력한다(§FR-04 Failed, §9 오프라인 가용성).

    직접 입력도 OcrRecord(임시 계층)를 남겨 원본과의 대응 관계를 유지한다.
    """
    record = OcrRecord(
        row_index=max((r.row_index for r in upload.ocr_records), default=0) + 1,
        field_index=0,
        wbs_id=wbs_id,
        item_type=item_type,
        raw_label=raw_label or "직접 입력",
        amount=None,
        quantity=None,
        unit=unit,
        value_basis=value_basis,
        confidence=Confidence.FAILED.value,
        confidence_reason="사용자 직접 입력",
        period_from=_parse_date(period_from),
        period_to=_parse_date(period_to),
        as_of_date=upload.as_of_date,
        high_impact=is_high_impact(item_type),
    )
    upload.ocr_records.append(record)
    session.flush()

    return apply_decision(
        session,
        record,
        RecordDecision(
            ocr_record_id=record.id,
            action=RecordAction.EDIT.value,
            amount=amount,
            quantity=quantity,
            unit=None if amount is None else "KRW",
            wbs_id=wbs_id,
            item_type=item_type,
            value_basis=value_basis,
            period_from=period_from,
            period_to=period_to,
            note="직접 입력",
        ),
        actor,
    )
