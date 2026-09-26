"""도메인 열거값(§6.2).

문자열 값은 DB·API·프런트엔드에서 그대로 사용하므로 변경 시 마이그레이션이 필요하다.
"""

from __future__ import annotations

from enum import Enum


class StrEnum(str, Enum):
    def __str__(self) -> str:  # pragma: no cover - 표시용
        return self.value


class ContractType(StrEnum):
    FIXED_PRICE = "fixed_price"
    TIME_AND_MATERIAL = "time_and_material"
    OTHER = "other"


class ScreenType(StrEnum):
    CONTRACT_INFO = "contract_info"
    TIME = "time"
    EXPENSE = "expense"
    BILLING = "billing"
    WIP = "wip"
    STAFFING = "staffing"
    BACKLOG = "backlog"
    LTD_ADJUSTMENT = "ltd_adjustment"
    OTHER = "other"


class UploadStatus(StrEnum):
    UPLOADED = "uploaded"
    OCR_DONE = "ocr_done"
    VERIFYING = "verifying"
    CONFIRMED = "confirmed"
    EXCLUDED = "excluded"


class ItemType(StrEnum):
    CONTRACT_AMOUNT = "contract_amount"
    TIME = "time"
    EXPENSE = "expense"
    OS = "os"
    #: 청구 완료액(실적)
    BILLING = "billing"
    NET_REVENUE = "net_revenue"
    WIP = "wip"
    LTD = "ltd"
    PROVISION = "provision"
    BACKLOG_MM = "backlog_mm"
    RATE = "rate"
    # ── Billing 화면 캡처 대응(§6.2 BILLING_PLAN 속성에 1:1 매핑).
    #    PRD의 item_type 열거값에 더해 청구 항목을 구분해 저장한다.
    #: 청구 예정액
    BILLING_PLANNED = "billing_planned"
    #: 미청구액(화면 표시값)
    BILLING_UNBILLED = "billing_unbilled"
    #: 청구 가능 경비
    BILLABLE_EXPENSE = "billable_expense"


#: 손익 사용액(누적 실적)에 합산되는 항목(§3.2 Time + Expense + OS)
COST_ITEM_TYPES = (ItemType.TIME, ItemType.EXPENSE, ItemType.OS)

#: Billing 화면에서 추출되는 청구 항목. 한 행에 이 중 하나라도 있으면 BillingPlan을 만든다.
BILLING_ITEM_TYPES = (
    ItemType.BILLING,
    ItemType.BILLING_PLANNED,
    ItemType.BILLING_UNBILLED,
    ItemType.BILLABLE_EXPENSE,
)

#: 금액이 아니라 수량·단가인 항목. 원(KRW) 정수 정규화 대상에서 제외한다.
NON_CURRENCY_ITEM_TYPES = (ItemType.BACKLOG_MM,)


class ValueBasis(StrEnum):
    CUMULATIVE = "cumulative"
    MONTHLY = "monthly"
    PERIOD = "period"


class Confidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    FAILED = "failed"


#: 확정 가능 여부 판정 시 사용하는 신뢰도 순서(낮을수록 위험)
CONFIDENCE_ORDER = {
    Confidence.FAILED: 0,
    Confidence.LOW: 1,
    Confidence.MEDIUM: 2,
    Confidence.HIGH: 3,
}


class RecordAction(StrEnum):
    CONFIRM = "confirm"
    EDIT = "edit"
    EXCLUDE = "exclude"
    REASSIGN = "reassign"
    DUPLICATE = "duplicate"
    FAILED = "failed"


#: 손익 계산에 반영되는 액션(§FR-10 확정값만 사용)
CALCULABLE_ACTIONS = (RecordAction.CONFIRM, RecordAction.EDIT, RecordAction.REASSIGN)


class IssueType(StrEnum):
    PERIOD_ERROR = "period_error"
    WBS_ATTRIBUTION = "wbs_attribution"
    DUPLICATE = "duplicate"
    UNIT_ERROR = "unit_error"
    TOTAL_MISMATCH = "total_mismatch"
    BILLING_ACTION = "billing_action"
    WIP_ACTION = "wip_action"
    BACKLOG_MISSING = "backlog_missing"


class IssueSeverity(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class IssueStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class ScenarioKind(StrEnum):
    BASE = "base"
    BEST = "best"
    WORST = "worst"


class DuplicateVerdict(StrEnum):
    #: 판정 Key 8종 전체 동일 → 자동 중복 후보(기본 제외)
    EXACT_DUPLICATE = "exact_duplicate"
    #: 동일 WBS·동일 기간·금액 상이 → 최신 Snapshot 후보
    LATEST_SNAPSHOT_CANDIDATE = "latest_snapshot_candidate"
    #: 동일 WBS·상이한 기간 → 별도 Snapshot
    SEPARATE_PERIOD = "separate_period"
    #: 누적값·월 발생액 혼재 → 유형 분리(합산 금지)
    BASIS_CONFLICT = "basis_conflict"
    #: 수정 전·후 화면 → change_link 연결
    CHANGE_LINK = "change_link"
    #: 중복 아님
    NEW = "new"
