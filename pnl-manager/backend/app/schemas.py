"""API 요청·응답 스키마."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from .enums import (
    ContractType,
    ItemType,
    RecordAction,
    ScenarioKind,
    ScreenType,
    ValueBasis,
)


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --------------------------------------------------------------- 프로젝트 마스터


class WbsCreate(BaseModel):
    code: str
    name: str | None = None
    valid_from: date | None = None
    valid_to: date | None = None


class ContractCreate(BaseModel):
    seq: int = Field(ge=0)
    amount: int = 0
    valid_from: date | None = None
    valid_to: date | None = None
    note: str | None = None
    wbs_list: list[WbsCreate] = Field(default_factory=list)


class EngagementCreate(BaseModel):
    name: str
    client: str
    engagement_code: str
    contract_type: ContractType = ContractType.FIXED_PRICE
    ep: str | None = None
    em: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    currency: str = "KRW"
    contracts: list[ContractCreate] = Field(default_factory=list)


class EngagementUpdate(BaseModel):
    name: str | None = None
    client: str | None = None
    contract_type: ContractType | None = None
    ep: str | None = None
    em: str | None = None
    start_date: date | None = None
    end_date: date | None = None


class WbsOut(ORMModel):
    id: int
    contract_id: int
    code: str
    name: str | None
    valid_from: date | None
    valid_to: date | None


class ContractOut(ORMModel):
    id: int
    seq: int
    amount: int
    valid_from: date | None
    valid_to: date | None
    note: str | None
    wbs_list: list[WbsOut] = Field(default_factory=list)


class EngagementOut(ORMModel):
    id: int
    name: str
    client: str
    engagement_code: str
    contract_type: str
    ep: str | None
    em: str | None
    start_date: date | None
    end_date: date | None
    currency: str
    contracts: list[ContractOut] = Field(default_factory=list)


# ------------------------------------------------------------------- 업로드·판독


class UploadOut(ORMModel):
    id: int
    engagement_id: int
    original_filename: str | None
    image_hash: str
    screen_type: str
    screen_type_source: str
    screen_title: str | None
    as_of_date: date | None
    uploaded_by: str | None
    uploaded_at: datetime
    status: str
    unit: str | None
    ocr_provider: str | None
    arithmetic_log: list | None
    warnings: list | None
    duplicate_of_upload_id: int | None
    confirmed_at: datetime | None


class UploadResult(BaseModel):
    upload: UploadOut
    duplicate: bool = False
    message: str | None = None


class ScreenTypeUpdate(BaseModel):
    screen_type: ScreenType


class OcrRecordOut(ORMModel):
    id: int
    upload_id: int
    row_index: int
    field_index: int
    wbs_code_raw: str | None
    wbs_id: int | None
    as_of_date: date | None
    period_from: date | None
    period_to: date | None
    item_type: str
    raw_label: str | None
    amount_raw: str | None
    amount: int | None
    quantity: float | None
    unit: str | None
    value_basis: str
    confidence: str
    confidence_reason: str | None
    bbox: list | None
    arithmetic_check: dict | None
    duplicate_verdict: str
    duplicate_of_record_id: int | None
    high_impact: bool
    needs_individual_confirmation: bool = False


class ConfirmedRecordOut(ORMModel):
    id: int
    ocr_record_id: int | None
    wbs_id: int | None
    item_type: str
    amount: int | None
    quantity: float | None
    unit: str | None
    period_from: date | None
    period_to: date | None
    value_basis: str
    action: str
    original_amount: int | None
    original_wbs_id: int | None
    confirmed_by: str | None
    confirmed_at: datetime
    note: str | None
    change_link_id: int | None


class VerificationView(BaseModel):
    upload: UploadOut
    records: list[OcrRecordOut]
    confirmed: list[ConfirmedRecordOut]
    arithmetic_log: list = Field(default_factory=list)
    snapshot_comparison: dict | None = None
    gate: dict


class DecisionIn(BaseModel):
    ocr_record_id: int
    action: RecordAction
    amount: int | float | str | None = None
    quantity: float | None = None
    unit: str | None = None
    wbs_id: int | None = None
    item_type: ItemType | None = None
    value_basis: ValueBasis | None = None
    period_from: str | None = None
    period_to: str | None = None
    note: str | None = None
    change_link_id: int | None = None


class DecisionBatch(BaseModel):
    decisions: list[DecisionIn]
    actor: str | None = None


class ManualRecordIn(BaseModel):
    item_type: ItemType
    wbs_id: int | None = None
    amount: int | None = None
    quantity: float | None = None
    unit: str | None = "KRW"
    value_basis: ValueBasis = ValueBasis.PERIOD
    period_from: str | None = None
    period_to: str | None = None
    raw_label: str | None = None
    actor: str | None = None


class ConfirmIn(BaseModel):
    actor: str | None = None
    force: bool = False
    create_snapshot: bool = True
    label: str | None = None


class ConfirmResult(BaseModel):
    upload: UploadOut
    snapshot_id: int | None = None
    issues_created: int = 0
    diff: dict | None = None
    pnl: dict | None = None


class OcrPayloadIn(BaseModel):
    """판독 결과 직접 주입(오프라인·수기 판독·테스트용)."""

    payload: dict


# --------------------------------------------------------------- 계산·Snapshot


class SnapshotOut(ORMModel):
    id: int
    engagement_id: int
    as_of_date: date | None
    created_at: datetime
    upload_ids: list
    formula_version: str
    label: str | None


class ScenarioIn(BaseModel):
    kind: ScenarioKind
    remaining_mm_delta_pct: float = 0.0
    rate_override: int | None = None
    end_date_extension_months: int = 0
    additional_contract_amount: int = 0
    expected_expense_os: int | None = None


class IssueOut(ORMModel):
    id: int
    engagement_id: int
    type: str
    severity: str
    title: str
    detail: str | None
    related_record_ids: list
    related_wbs_id: int | None
    suggested_actions: list
    selected_action: str | None
    status: str
    created_at: datetime
    resolved_at: datetime | None


class IssueResolveIn(BaseModel):
    selected_action: str
    target_wbs_id: int | None = None
    actor: str | None = None


class StaffingIn(BaseModel):
    wbs_id: int
    person_or_grade: str | None = None
    month: str | None = None
    fte_rate: float | None = None
    remaining_mm: float = 0.0
    rate: int = 0
    expected_time: int | None = None


class BillingIn(BaseModel):
    wbs_id: int
    planned_amount: int = 0
    billed_amount: int = 0
    billing_date: date | None = None
    unbilled_amount: int | None = None
    billable_expense: int = 0
