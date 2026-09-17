"""데이터 모델(§6.2).

데이터 3계층(§6.1)을 테이블로 분리한다.
  - OCR 판독값(임시): OcrRecord — 최초 판독값을 불변 보존
  - 사용자 확인값(확정): ConfirmedRecord — 손익 계산의 유일한 입력
  - 시스템 계산값(파생): Snapshot / SnapshotValue / Scenario — 산식 버전과 함께 저장
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from ..enums import (
    Confidence,
    ContractType,
    DuplicateVerdict,
    IssueSeverity,
    IssueStatus,
    IssueType,
    ItemType,
    RecordAction,
    ScenarioKind,
    ScreenType,
    UploadStatus,
    ValueBasis,
)


class Base(DeclarativeBase):
    pass


def _now() -> datetime:
    return datetime.now()


class Engagement(Base):
    __tablename__ = "engagement"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    client: Mapped[str] = mapped_column(String(200))
    engagement_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    contract_type: Mapped[str] = mapped_column(String(32), default=ContractType.FIXED_PRICE.value)
    ep: Mapped[str | None] = mapped_column(String(100), default=None)
    em: Mapped[str | None] = mapped_column(String(100), default=None)
    start_date: Mapped[date | None] = mapped_column(Date, default=None)
    end_date: Mapped[date | None] = mapped_column(Date, default=None)
    currency: Mapped[str] = mapped_column(String(8), default="KRW")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    contracts: Mapped[list["Contract"]] = relationship(
        back_populates="engagement", cascade="all, delete-orphan", order_by="Contract.seq"
    )
    uploads: Mapped[list["Upload"]] = relationship(
        back_populates="engagement", cascade="all, delete-orphan"
    )
    snapshots: Mapped[list["Snapshot"]] = relationship(
        back_populates="engagement", cascade="all, delete-orphan", order_by="Snapshot.created_at"
    )
    issues: Mapped[list["Issue"]] = relationship(
        back_populates="engagement", cascade="all, delete-orphan"
    )
    scenarios: Mapped[list["Scenario"]] = relationship(
        back_populates="engagement", cascade="all, delete-orphan"
    )


class Contract(Base):
    """계약변경 차수. seq=0이 최초 계약이고 1 이상이 변경계약이다(§3.1)."""

    __tablename__ = "contract"
    __table_args__ = (UniqueConstraint("engagement_id", "seq", name="uq_contract_seq"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    engagement_id: Mapped[int] = mapped_column(ForeignKey("engagement.id", ondelete="CASCADE"))
    seq: Mapped[int] = mapped_column(Integer)
    amount: Mapped[int] = mapped_column(Integer, default=0)  # 원(KRW) 정수
    valid_from: Mapped[date | None] = mapped_column(Date, default=None)
    valid_to: Mapped[date | None] = mapped_column(Date, default=None)
    note: Mapped[str | None] = mapped_column(Text, default=None)

    engagement: Mapped[Engagement] = relationship(back_populates="contracts")
    wbs_list: Mapped[list["Wbs"]] = relationship(
        back_populates="contract", cascade="all, delete-orphan", order_by="Wbs.code"
    )


class Wbs(Base):
    """비용 귀속 단위. 계약 차수의 유효기간을 상속한다(§FR-01)."""

    __tablename__ = "wbs"
    __table_args__ = (UniqueConstraint("contract_id", "code", name="uq_wbs_code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("contract.id", ondelete="CASCADE"))
    code: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str | None] = mapped_column(String(200), default=None)
    valid_from: Mapped[date | None] = mapped_column(Date, default=None)
    valid_to: Mapped[date | None] = mapped_column(Date, default=None)

    contract: Mapped[Contract] = relationship(back_populates="wbs_list")

    @property
    def engagement_id(self) -> int:
        return self.contract.engagement_id

    @property
    def effective_valid_from(self) -> date | None:
        return self.valid_from or self.contract.valid_from

    @property
    def effective_valid_to(self) -> date | None:
        return self.valid_to or self.contract.valid_to


class Upload(Base):
    """화면 캡처 업로드 단위(§FR-02)."""

    __tablename__ = "upload"

    id: Mapped[int] = mapped_column(primary_key=True)
    engagement_id: Mapped[int] = mapped_column(ForeignKey("engagement.id", ondelete="CASCADE"))
    file_path: Mapped[str] = mapped_column(String(500))
    original_filename: Mapped[str | None] = mapped_column(String(300), default=None)
    image_hash: Mapped[str] = mapped_column(String(64), index=True)
    screen_type: Mapped[str] = mapped_column(String(32), default=ScreenType.OTHER.value)
    screen_type_source: Mapped[str] = mapped_column(String(16), default="user")  # user | auto
    screen_title: Mapped[str | None] = mapped_column(String(300), default=None)
    as_of_date: Mapped[date | None] = mapped_column(Date, default=None)
    uploaded_by: Mapped[str | None] = mapped_column(String(100), default=None)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    status: Mapped[str] = mapped_column(String(16), default=UploadStatus.UPLOADED.value)
    unit: Mapped[str | None] = mapped_column(String(16), default=None)
    ocr_provider: Mapped[str | None] = mapped_column(String(32), default=None)
    ocr_payload: Mapped[dict | None] = mapped_column(JSON, default=None)  # 최초 판독 원문 보존
    arithmetic_log: Mapped[list | None] = mapped_column(JSON, default=None)  # §FR-06 검증 로그
    duplicate_of_upload_id: Mapped[int | None] = mapped_column(
        ForeignKey("upload.id", ondelete="SET NULL"), default=None
    )
    warnings: Mapped[list | None] = mapped_column(JSON, default=None)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    confirmed_by: Mapped[str | None] = mapped_column(String(100), default=None)

    engagement: Mapped[Engagement] = relationship(back_populates="uploads")
    ocr_records: Mapped[list["OcrRecord"]] = relationship(
        back_populates="upload", cascade="all, delete-orphan", order_by="OcrRecord.row_index"
    )


class OcrRecord(Base):
    """OCR 판독값(임시 데이터). 최초 판독값은 수정하지 않는다(§6.1)."""

    __tablename__ = "ocr_record"

    id: Mapped[int] = mapped_column(primary_key=True)
    upload_id: Mapped[int] = mapped_column(ForeignKey("upload.id", ondelete="CASCADE"))
    row_index: Mapped[int] = mapped_column(Integer, default=0)
    field_index: Mapped[int] = mapped_column(Integer, default=0)
    wbs_code_raw: Mapped[str | None] = mapped_column(String(64), default=None)
    wbs_id: Mapped[int | None] = mapped_column(
        ForeignKey("wbs.id", ondelete="SET NULL"), default=None
    )
    as_of_date: Mapped[date | None] = mapped_column(Date, default=None)
    period_from: Mapped[date | None] = mapped_column(Date, default=None)
    period_to: Mapped[date | None] = mapped_column(Date, default=None)
    item_type: Mapped[str] = mapped_column(String(32))
    raw_label: Mapped[str | None] = mapped_column(String(200), default=None)
    amount_raw: Mapped[str | None] = mapped_column(String(64), default=None)
    amount: Mapped[int | None] = mapped_column(Integer, default=None)  # 원(KRW) 정수 정규화값
    quantity: Mapped[float | None] = mapped_column(Float, default=None)  # MM·시간 등 비금액 값
    unit: Mapped[str | None] = mapped_column(String(16), default=None)
    value_basis: Mapped[str] = mapped_column(String(16), default=ValueBasis.PERIOD.value)
    confidence: Mapped[str] = mapped_column(String(16), default=Confidence.MEDIUM.value)
    confidence_reason: Mapped[str | None] = mapped_column(Text, default=None)
    bbox: Mapped[list | None] = mapped_column(JSON, default=None)  # [x, y, w, h] 0~1 비율
    arithmetic_check: Mapped[dict | None] = mapped_column(JSON, default=None)
    duplicate_verdict: Mapped[str] = mapped_column(String(32), default=DuplicateVerdict.NEW.value)
    duplicate_of_record_id: Mapped[int | None] = mapped_column(Integer, default=None)
    high_impact: Mapped[bool] = mapped_column(Boolean, default=False)

    upload: Mapped[Upload] = relationship(back_populates="ocr_records")
    wbs: Mapped[Wbs | None] = relationship()
    confirmed: Mapped["ConfirmedRecord | None"] = relationship(
        back_populates="ocr_record", cascade="all, delete-orphan", uselist=False
    )


class ConfirmedRecord(Base):
    """사용자 확인값(확정 데이터). 손익 계산의 유일한 입력이다(§6.1)."""

    __tablename__ = "confirmed_record"

    id: Mapped[int] = mapped_column(primary_key=True)
    ocr_record_id: Mapped[int | None] = mapped_column(
        ForeignKey("ocr_record.id", ondelete="CASCADE"), default=None
    )
    engagement_id: Mapped[int] = mapped_column(ForeignKey("engagement.id", ondelete="CASCADE"))
    upload_id: Mapped[int | None] = mapped_column(
        ForeignKey("upload.id", ondelete="CASCADE"), default=None
    )
    wbs_id: Mapped[int | None] = mapped_column(
        ForeignKey("wbs.id", ondelete="SET NULL"), default=None
    )
    item_type: Mapped[str] = mapped_column(String(32))
    amount: Mapped[int | None] = mapped_column(Integer, default=None)
    quantity: Mapped[float | None] = mapped_column(Float, default=None)
    unit: Mapped[str | None] = mapped_column(String(16), default=None)
    as_of_date: Mapped[date | None] = mapped_column(Date, default=None)
    period_from: Mapped[date | None] = mapped_column(Date, default=None)
    period_to: Mapped[date | None] = mapped_column(Date, default=None)
    value_basis: Mapped[str] = mapped_column(String(16), default=ValueBasis.PERIOD.value)
    action: Mapped[str] = mapped_column(String(16), default=RecordAction.CONFIRM.value)
    original_amount: Mapped[int | None] = mapped_column(Integer, default=None)
    original_wbs_id: Mapped[int | None] = mapped_column(Integer, default=None)
    confirmed_by: Mapped[str | None] = mapped_column(String(100), default=None)
    confirmed_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    note: Mapped[str | None] = mapped_column(Text, default=None)
    change_link_id: Mapped[int | None] = mapped_column(Integer, default=None)

    ocr_record: Mapped[OcrRecord | None] = relationship(back_populates="confirmed")
    wbs: Mapped[Wbs | None] = relationship()

    @property
    def is_calculable(self) -> bool:
        from ..enums import CALCULABLE_ACTIONS

        return self.action in {a.value for a in CALCULABLE_ACTIONS}


class Snapshot(Base):
    """확정 시점별 보존 단위(§FR-08). 기존 Snapshot은 덮어쓰지 않는다."""

    __tablename__ = "snapshot"

    id: Mapped[int] = mapped_column(primary_key=True)
    engagement_id: Mapped[int] = mapped_column(ForeignKey("engagement.id", ondelete="CASCADE"))
    as_of_date: Mapped[date | None] = mapped_column(Date, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    upload_ids: Mapped[list] = mapped_column(JSON, default=list)
    formula_version: Mapped[str] = mapped_column(String(16), default="1.0.0")
    label: Mapped[str | None] = mapped_column(String(200), default=None)
    result: Mapped[dict | None] = mapped_column(JSON, default=None)  # 계산 결과 캐시(파생)

    engagement: Mapped[Engagement] = relationship(back_populates="snapshots")
    values: Mapped[list["SnapshotValue"]] = relationship(
        back_populates="snapshot", cascade="all, delete-orphan"
    )


class SnapshotValue(Base):
    __tablename__ = "snapshot_value"

    id: Mapped[int] = mapped_column(primary_key=True)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("snapshot.id", ondelete="CASCADE"))
    wbs_id: Mapped[int | None] = mapped_column(Integer, default=None)
    wbs_code: Mapped[str | None] = mapped_column(String(64), default=None)
    item_type: Mapped[str] = mapped_column(String(32))
    amount: Mapped[int | None] = mapped_column(Integer, default=None)
    quantity: Mapped[float | None] = mapped_column(Float, default=None)
    value_basis: Mapped[str] = mapped_column(String(16), default=ValueBasis.PERIOD.value)
    period_from: Mapped[date | None] = mapped_column(Date, default=None)
    period_to: Mapped[date | None] = mapped_column(Date, default=None)
    as_of_date: Mapped[date | None] = mapped_column(Date, default=None)
    confirmed_record_id: Mapped[int | None] = mapped_column(Integer, default=None)

    snapshot: Mapped[Snapshot] = relationship(back_populates="values")


class StaffingPlan(Base):
    """Backlog·Staffing 화면 기반 잔여 투입 계획(§3.1)."""

    __tablename__ = "staffing_plan"

    id: Mapped[int] = mapped_column(primary_key=True)
    wbs_id: Mapped[int] = mapped_column(ForeignKey("wbs.id", ondelete="CASCADE"))
    person_or_grade: Mapped[str | None] = mapped_column(String(100), default=None)
    month: Mapped[str | None] = mapped_column(String(7), default=None)  # YYYY-MM
    fte_rate: Mapped[float | None] = mapped_column(Float, default=None)
    remaining_mm: Mapped[float] = mapped_column(Float, default=0.0)
    rate: Mapped[int] = mapped_column(Integer, default=0)  # MM당 원(KRW)
    expected_time: Mapped[int | None] = mapped_column(Integer, default=None)
    source_upload_id: Mapped[int | None] = mapped_column(Integer, default=None)

    wbs: Mapped[Wbs] = relationship()

    @property
    def computed_expected_time(self) -> int:
        if self.expected_time is not None:
            return int(self.expected_time)
        return int(round(self.remaining_mm * self.rate))


class BillingPlan(Base):
    __tablename__ = "billing_plan"

    id: Mapped[int] = mapped_column(primary_key=True)
    wbs_id: Mapped[int] = mapped_column(ForeignKey("wbs.id", ondelete="CASCADE"))
    planned_amount: Mapped[int] = mapped_column(Integer, default=0)
    billed_amount: Mapped[int] = mapped_column(Integer, default=0)
    billing_date: Mapped[date | None] = mapped_column(Date, default=None)
    unbilled_amount: Mapped[int | None] = mapped_column(Integer, default=None)
    billable_expense: Mapped[int] = mapped_column(Integer, default=0)
    source_upload_id: Mapped[int | None] = mapped_column(Integer, default=None)

    wbs: Mapped[Wbs] = relationship()

    @property
    def computed_unbilled(self) -> int:
        if self.unbilled_amount is not None:
            return int(self.unbilled_amount)
        return int(self.planned_amount) - int(self.billed_amount)


class LtdAdjustment(Base):
    __tablename__ = "ltd_adjustment"

    id: Mapped[int] = mapped_column(primary_key=True)
    wbs_id: Mapped[int] = mapped_column(ForeignKey("wbs.id", ondelete="CASCADE"))
    adjust_date: Mapped[date | None] = mapped_column(Date, default=None)
    amount: Mapped[int] = mapped_column(Integer, default=0)
    note: Mapped[str | None] = mapped_column(Text, default=None)
    source_upload_id: Mapped[int | None] = mapped_column(Integer, default=None)

    wbs: Mapped[Wbs] = relationship()


class Issue(Base):
    """이상징후·조치사항(§FR-09, §FR-12)."""

    __tablename__ = "issue"

    id: Mapped[int] = mapped_column(primary_key=True)
    engagement_id: Mapped[int] = mapped_column(ForeignKey("engagement.id", ondelete="CASCADE"))
    type: Mapped[str] = mapped_column(String(32))
    severity: Mapped[str] = mapped_column(String(16), default=IssueSeverity.MEDIUM.value)
    title: Mapped[str] = mapped_column(String(300))
    detail: Mapped[str | None] = mapped_column(Text, default=None)
    related_record_ids: Mapped[list] = mapped_column(JSON, default=list)
    related_wbs_id: Mapped[int | None] = mapped_column(Integer, default=None)
    suggested_actions: Mapped[list] = mapped_column(JSON, default=list)
    selected_action: Mapped[str | None] = mapped_column(String(64), default=None)
    status: Mapped[str] = mapped_column(String(16), default=IssueStatus.OPEN.value)
    dedup_key: Mapped[str | None] = mapped_column(String(200), index=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)

    engagement: Mapped[Engagement] = relationship(back_populates="issues")


class Scenario(Base):
    __tablename__ = "scenario"
    __table_args__ = (UniqueConstraint("engagement_id", "kind", name="uq_scenario_kind"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    engagement_id: Mapped[int] = mapped_column(ForeignKey("engagement.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(16), default=ScenarioKind.BASE.value)
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict | None] = mapped_column(JSON, default=None)
    computed_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    engagement: Mapped[Engagement] = relationship(back_populates="scenarios")


class AuditLog(Base):
    """모든 확정·수정·제외·재분류 기록(§9 감사 추적)."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[int | None] = mapped_column(Integer, default=None)
    field: Mapped[str | None] = mapped_column(String(64), default=None)
    before: Mapped[str | None] = mapped_column(Text, default=None)
    after: Mapped[str | None] = mapped_column(Text, default=None)
    actor: Mapped[str | None] = mapped_column(String(100), default=None)
    at: Mapped[datetime] = mapped_column(DateTime, default=_now)


Index("ix_confirmed_engagement_item", ConfirmedRecord.engagement_id, ConfirmedRecord.item_type)
Index("ix_ocr_upload_row", OcrRecord.upload_id, OcrRecord.row_index)
Index("ix_snapshot_value_lookup", SnapshotValue.snapshot_id, SnapshotValue.item_type)

__all__ = [
    "AuditLog",
    "Base",
    "BillingPlan",
    "ConfirmedRecord",
    "Contract",
    "Engagement",
    "Issue",
    "LtdAdjustment",
    "OcrRecord",
    "Scenario",
    "Snapshot",
    "SnapshotValue",
    "StaffingPlan",
    "Upload",
    "Wbs",
]
