"""프로젝트 마스터 관리 API(§FR-01)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db import get_session
from ..models import BillingPlan, Contract, Engagement, StaffingPlan, Wbs
from ..schemas import (
    BillingIn,
    ContractCreate,
    ContractOut,
    EngagementCreate,
    EngagementOut,
    EngagementUpdate,
    StaffingIn,
    WbsCreate,
    WbsOut,
)
from ..services import audit

router = APIRouter(tags=["engagements"])


def _overlaps(a_from, a_to, b_from, b_to) -> bool:
    """유효기간 겹침 검사(§7 프로젝트 마스터)."""
    if a_from is None or a_to is None or b_from is None or b_to is None:
        return False
    return a_from <= b_to and b_from <= a_to


@router.post("/engagements", response_model=EngagementOut, status_code=201)
def create_engagement(payload: EngagementCreate, session: Session = Depends(get_session)):
    existing = session.execute(
        select(Engagement).where(Engagement.engagement_code == payload.engagement_code)
    ).scalars().first()
    if existing is not None:
        raise HTTPException(409, f"Engagement Code {payload.engagement_code}가 이미 있습니다.")

    engagement = Engagement(
        name=payload.name,
        client=payload.client,
        engagement_code=payload.engagement_code,
        contract_type=payload.contract_type.value,
        ep=payload.ep,
        em=payload.em,
        start_date=payload.start_date,
        end_date=payload.end_date,
        currency=payload.currency,
    )
    session.add(engagement)
    session.flush()

    for contract_payload in sorted(payload.contracts, key=lambda c: c.seq):
        _add_contract(session, engagement, contract_payload)

    session.flush()
    audit.log(session, entity="engagement", entity_id=engagement.id, field="created", after=payload.engagement_code)
    return engagement


def _add_contract(session: Session, engagement: Engagement, payload: ContractCreate) -> Contract:
    for other in engagement.contracts:
        if other.seq == payload.seq:
            raise HTTPException(409, f"계약 차수 {payload.seq}가 이미 있습니다.")
        if _overlaps(payload.valid_from, payload.valid_to, other.valid_from, other.valid_to):
            raise HTTPException(
                409,
                f"계약 차수 {payload.seq}의 유효기간이 차수 {other.seq}"
                f"({other.valid_from} ~ {other.valid_to})와 겹칩니다.",
            )
    contract = Contract(
        engagement_id=engagement.id,
        seq=payload.seq,
        amount=payload.amount,
        valid_from=payload.valid_from,
        valid_to=payload.valid_to,
        note=payload.note,
    )
    session.add(contract)
    session.flush()
    for wbs_payload in payload.wbs_list:
        _add_wbs(session, contract, wbs_payload)
    engagement.contracts.append(contract)
    return contract


def _add_wbs(session: Session, contract: Contract, payload: WbsCreate) -> Wbs:
    # WBS Code는 계약 차수의 유효기간을 상속한다(§FR-01).
    wbs = Wbs(
        contract_id=contract.id,
        code=payload.code,
        name=payload.name,
        valid_from=payload.valid_from or contract.valid_from,
        valid_to=payload.valid_to or contract.valid_to,
    )
    session.add(wbs)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(409, f"WBS Code {payload.code}가 이미 있습니다.") from exc
    return wbs


@router.get("/engagements", response_model=list[EngagementOut])
def list_engagements(session: Session = Depends(get_session)):
    return list(session.execute(select(Engagement).order_by(Engagement.id)).scalars())


@router.get("/engagements/{engagement_id}", response_model=EngagementOut)
def get_engagement_detail(engagement_id: int, session: Session = Depends(get_session)):
    engagement = session.get(Engagement, engagement_id)
    if engagement is None:
        raise HTTPException(404, f"Engagement #{engagement_id}를 찾을 수 없습니다.")
    return engagement


@router.patch("/engagements/{engagement_id}", response_model=EngagementOut)
def update_engagement(
    engagement_id: int, payload: EngagementUpdate, session: Session = Depends(get_session)
):
    engagement = session.get(Engagement, engagement_id)
    if engagement is None:
        raise HTTPException(404, f"Engagement #{engagement_id}를 찾을 수 없습니다.")
    for field, value in payload.model_dump(exclude_none=True).items():
        before = getattr(engagement, field)
        setattr(engagement, field, value.value if hasattr(value, "value") else value)
        audit.log(
            session,
            entity="engagement",
            entity_id=engagement.id,
            field=field,
            before=before,
            after=value,
        )
    session.flush()
    return engagement


@router.post("/engagements/{engagement_id}/contracts", response_model=ContractOut, status_code=201)
def add_contract(
    engagement_id: int, payload: ContractCreate, session: Session = Depends(get_session)
):
    engagement = session.get(Engagement, engagement_id)
    if engagement is None:
        raise HTTPException(404, f"Engagement #{engagement_id}를 찾을 수 없습니다.")
    contract = _add_contract(session, engagement, payload)
    session.flush()
    return contract


@router.post("/contracts/{contract_id}/wbs", response_model=WbsOut, status_code=201)
def add_wbs(contract_id: int, payload: WbsCreate, session: Session = Depends(get_session)):
    contract = session.get(Contract, contract_id)
    if contract is None:
        raise HTTPException(404, f"Contract #{contract_id}를 찾을 수 없습니다.")
    return _add_wbs(session, contract, payload)


@router.get("/engagements/{engagement_id}/wbs", response_model=list[WbsOut])
def list_wbs(engagement_id: int, session: Session = Depends(get_session)):
    stmt = (
        select(Wbs)
        .join(Contract, Wbs.contract_id == Contract.id)
        .where(Contract.engagement_id == engagement_id)
        .order_by(Contract.seq, Wbs.code)
    )
    return list(session.execute(stmt).scalars())


@router.post("/engagements/{engagement_id}/staffing", status_code=201)
def upsert_staffing(
    engagement_id: int, payload: list[StaffingIn], session: Session = Depends(get_session)
):
    """Backlog 화면을 캡처하지 못한 경우 잔여 투입 계획을 직접 입력한다."""
    created = []
    for row in payload:
        plan = StaffingPlan(
            wbs_id=row.wbs_id,
            person_or_grade=row.person_or_grade,
            month=row.month,
            fte_rate=row.fte_rate,
            remaining_mm=row.remaining_mm,
            rate=row.rate,
            expected_time=row.expected_time,
        )
        session.add(plan)
        created.append(plan)
    session.flush()
    return {"created": len(created)}


@router.post("/engagements/{engagement_id}/billing", status_code=201)
def upsert_billing(
    engagement_id: int, payload: list[BillingIn], session: Session = Depends(get_session)
):
    created = []
    for row in payload:
        plan = BillingPlan(
            wbs_id=row.wbs_id,
            planned_amount=row.planned_amount,
            billed_amount=row.billed_amount,
            billing_date=row.billing_date,
            unbilled_amount=row.unbilled_amount,
            billable_expense=row.billable_expense,
        )
        session.add(plan)
        created.append(plan)
    session.flush()
    return {"created": len(created)}
