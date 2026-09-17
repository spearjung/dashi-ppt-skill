"""손익 산식(§3.2).

계산 단위 계층: Engagement → 계약변경 차수 → WBS → 기간 → 항목.

입력은 확정값(ConfirmedRecord)만 사용한다(§FR-10). 누적값(cumulative)과
월 발생액(monthly·period)은 합산하지 않고, 한 항목에 두 기준이 함께 있으면
누적값을 채택하고 경고를 남긴다(§3.1).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from ..enums import COST_ITEM_TYPES, ItemType, ValueBasis

#: 산식 버전. 파생 데이터에 함께 저장한다(§FR-10).
FORMULA_VERSION = "1.0.0"

_COST_KEYS = tuple(i.value for i in COST_ITEM_TYPES)


# --------------------------------------------------------------------------- 입력


@dataclass(slots=True)
class CostRecord:
    """확정된 항목 값 하나."""

    wbs_id: int | None
    item_type: str
    amount: int | None = None
    quantity: float | None = None
    value_basis: str = ValueBasis.PERIOD.value
    period_from: date | None = None
    period_to: date | None = None
    as_of_date: date | None = None
    confirmed_at: date | None = None


@dataclass(slots=True)
class ContractInput:
    id: int
    seq: int
    amount: int
    valid_from: date | None = None
    valid_to: date | None = None


@dataclass(slots=True)
class WbsInput:
    id: int
    code: str
    contract_id: int
    contract_seq: int
    valid_from: date | None = None
    valid_to: date | None = None


@dataclass(slots=True)
class StaffingInput:
    wbs_id: int
    remaining_mm: float = 0.0
    rate: int = 0
    expected_time: int | None = None
    month: str | None = None

    @property
    def time_amount(self) -> int:
        if self.expected_time is not None:
            return int(self.expected_time)
        return int(round(self.remaining_mm * self.rate))


@dataclass(slots=True)
class BillingInput:
    wbs_id: int
    planned_amount: int = 0
    billed_amount: int = 0
    unbilled_amount: int | None = None
    billable_expense: int = 0

    @property
    def unbilled(self) -> int:
        if self.unbilled_amount is not None:
            return int(self.unbilled_amount)
        return int(self.planned_amount) - int(self.billed_amount)


@dataclass(slots=True)
class LtdInput:
    wbs_id: int
    amount: int = 0


@dataclass(slots=True)
class PnlInput:
    engagement_id: int
    contract_type: str
    contracts: list[ContractInput]
    wbs_list: list[WbsInput]
    records: list[CostRecord]
    staffing: list[StaffingInput] = field(default_factory=list)
    billing: list[BillingInput] = field(default_factory=list)
    ltd_adjustments: list[LtdInput] = field(default_factory=list)
    #: WBS별 잔여 기간 예상 Expense·OS. Backlog 화면이나 시나리오 변수에서 온다.
    expected_expense_os: dict[int, int] = field(default_factory=dict)
    snapshot_id: int | None = None
    as_of_date: date | None = None


# --------------------------------------------------------------------------- 출력


@dataclass(slots=True)
class WbsResult:
    wbs_id: int
    code: str
    contract_seq: int
    amounts: dict[str, int]
    cumulative_usage: int
    billing: int
    current_wip: int
    screen_wip: int | None
    wip_mismatch: int | None
    remaining_mm: float
    remaining_input_estimate: int
    backlog_entered: bool
    eac: int
    allocated_contract_amount: int
    final_expected_balance: int
    expected_end_wip: int
    ltd_required: int
    ltd_adjusted: int
    ltd_outstanding: int
    unbilled_amount: int
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "wbs_id": self.wbs_id,
            "code": self.code,
            "contract_seq": self.contract_seq,
            "amounts": self.amounts,
            "cumulative_usage": self.cumulative_usage,
            "billing": self.billing,
            "current_wip": self.current_wip,
            "screen_wip": self.screen_wip,
            "wip_mismatch": self.wip_mismatch,
            "remaining_mm": self.remaining_mm,
            "remaining_input_estimate": self.remaining_input_estimate,
            "backlog_entered": self.backlog_entered,
            "eac": self.eac,
            "allocated_contract_amount": self.allocated_contract_amount,
            "final_expected_balance": self.final_expected_balance,
            "expected_end_wip": self.expected_end_wip,
            "ltd_required": self.ltd_required,
            "ltd_adjusted": self.ltd_adjusted,
            "ltd_outstanding": self.ltd_outstanding,
            "unbilled_amount": self.unbilled_amount,
            "warnings": self.warnings,
        }


@dataclass(slots=True)
class ContractResult:
    contract_id: int
    seq: int
    amount: int
    cumulative_usage: int
    eac: int
    balance: int
    final_expected_balance: int
    ltd_required: int
    ltd_adjusted: int
    ltd_outstanding: int
    wbs_ids: list[int]

    def as_dict(self) -> dict:
        return {
            "contract_id": self.contract_id,
            "seq": self.seq,
            "amount": self.amount,
            "cumulative_usage": self.cumulative_usage,
            "eac": self.eac,
            "balance": self.balance,
            "final_expected_balance": self.final_expected_balance,
            "ltd_required": self.ltd_required,
            "ltd_adjusted": self.ltd_adjusted,
            "ltd_outstanding": self.ltd_outstanding,
            "wbs_ids": self.wbs_ids,
        }


@dataclass(slots=True)
class EngagementPnl:
    engagement_id: int
    formula_version: str
    snapshot_id: int | None
    total_contract_amount: int
    cumulative_usage: int
    total_billing: int
    current_wip: int
    screen_wip: int | None
    wip_mismatch: int | None
    contract_balance: int
    remaining_input_estimate: int
    backlog_entered: bool
    provisional: bool
    eac: int
    final_expected_balance: int
    expected_end_wip: int
    ltd_required: int
    ltd_adjusted: int
    ltd_outstanding: int
    additional_contract_needed: int
    required_mm_reduction: float | None
    weighted_average_rate: int | None
    expected_margin_rate: float | None
    unbilled_amount: int
    contracts: list[ContractResult]
    wbs_results: list[WbsResult]
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "engagement_id": self.engagement_id,
            "formula_version": self.formula_version,
            "snapshot_id": self.snapshot_id,
            "total_contract_amount": self.total_contract_amount,
            "cumulative_usage": self.cumulative_usage,
            "total_billing": self.total_billing,
            "current_wip": self.current_wip,
            "screen_wip": self.screen_wip,
            "wip_mismatch": self.wip_mismatch,
            "contract_balance": self.contract_balance,
            "remaining_input_estimate": self.remaining_input_estimate,
            "backlog_entered": self.backlog_entered,
            "provisional": self.provisional,
            "eac": self.eac,
            "final_expected_balance": self.final_expected_balance,
            "expected_end_wip": self.expected_end_wip,
            "ltd_required": self.ltd_required,
            "ltd_adjusted": self.ltd_adjusted,
            "ltd_outstanding": self.ltd_outstanding,
            "additional_contract_needed": self.additional_contract_needed,
            "required_mm_reduction": self.required_mm_reduction,
            "weighted_average_rate": self.weighted_average_rate,
            "expected_margin_rate": self.expected_margin_rate,
            "unbilled_amount": self.unbilled_amount,
            "contracts": [c.as_dict() for c in self.contracts],
            "wbs_results": [w.as_dict() for w in self.wbs_results],
            "warnings": self.warnings,
        }


# --------------------------------------------------------------------------- 집계


def aggregate_amounts(
    records: list[CostRecord],
) -> tuple[dict[tuple[int | None, str], int], dict[tuple[int | None, str], float], list[str]]:
    """(wbs_id, item_type) 별 금액·수량을 값 기준에 맞게 집계한다.

    cumulative 은 조회 기준일이 가장 늦은 한 건만 사용하고,
    period·monthly 는 기간별로 합산한다(동일 기간 중복은 최신 확정값 채택).
    """
    buckets: dict[tuple[int | None, str], dict] = {}
    warnings: list[str] = []

    for rec in records:
        key = (rec.wbs_id, rec.item_type)
        bucket = buckets.setdefault(key, {"cumulative": None, "periodic": []})
        if rec.value_basis == ValueBasis.CUMULATIVE.value:
            # 누적값은 조회 기준일이 가장 늦은 한 건만 사용한다(중복 합산 방지).
            current = bucket["cumulative"]
            if current is None or _as_of(rec) >= _as_of(current):
                bucket["cumulative"] = rec
        else:
            # 기간·월 발생액은 모두 합산한다. 동일 기간 중복은 확정 단계의
            # 중복 판정(§FR-07)에서 제외·대체 처리되므로 여기서 덮어쓰지 않는다.
            # 재분류로 같은 기간의 값이 한 WBS에 모이는 경우를 합산해야 한다.
            bucket["periodic"].append(rec)

    amounts: dict[tuple[int | None, str], int] = {}
    quantities: dict[tuple[int | None, str], float] = {}
    for key, bucket in buckets.items():
        cumulative = bucket["cumulative"]
        periodic = list(bucket["periodic"])
        if cumulative is not None and periodic:
            warnings.append(
                f"{key[1]} 항목에 누적값과 기간 발생액이 함께 확정되어 있어 "
                f"누적값을 채택했습니다(합산 금지, §3.1)."
            )
            chosen = [cumulative]
        elif cumulative is not None:
            chosen = [cumulative]
        else:
            chosen = periodic
        amount_total = sum(r.amount for r in chosen if r.amount is not None)
        quantity_total = sum(r.quantity for r in chosen if r.quantity is not None)
        if any(r.amount is not None for r in chosen):
            amounts[key] = int(amount_total)
        if any(r.quantity is not None for r in chosen):
            quantities[key] = float(quantity_total)
    return amounts, quantities, warnings


def _as_of(rec: CostRecord) -> date:
    return rec.as_of_date or rec.period_to or rec.period_from or date.min


# --------------------------------------------------------------------------- 계산


def compute_pnl(data: PnlInput) -> EngagementPnl:
    """§3.2 산식을 계약 차수·WBS 단위로 전개해 손익을 계산한다."""
    amounts, quantities, agg_warnings = aggregate_amounts(data.records)
    warnings = list(agg_warnings)

    contracts_by_id = {c.id: c for c in data.contracts}
    staffing_by_wbs: dict[int, list[StaffingInput]] = {}
    for plan in data.staffing:
        staffing_by_wbs.setdefault(plan.wbs_id, []).append(plan)
    billing_by_wbs: dict[int, list[BillingInput]] = {}
    for plan in data.billing:
        billing_by_wbs.setdefault(plan.wbs_id, []).append(plan)
    ltd_by_wbs: dict[int, int] = {}
    for adj in data.ltd_adjustments:
        ltd_by_wbs[adj.wbs_id] = ltd_by_wbs.get(adj.wbs_id, 0) + int(adj.amount)

    # 차수별 계약금액을 소속 WBS에 사용액 비율로 배분한다. WBS가 하나면 전액 배분된다.
    usage_by_wbs: dict[int, int] = {}
    for wbs in data.wbs_list:
        usage_by_wbs[wbs.id] = sum(amounts.get((wbs.id, key), 0) for key in _COST_KEYS)

    wbs_by_contract: dict[int, list[WbsInput]] = {}
    for wbs in data.wbs_list:
        wbs_by_contract.setdefault(wbs.contract_id, []).append(wbs)

    allocation: dict[int, int] = {}
    for contract_id, members in wbs_by_contract.items():
        contract = contracts_by_id.get(contract_id)
        total_amount = contract.amount if contract else 0
        member_usage = {w.id: usage_by_wbs.get(w.id, 0) for w in members}
        usage_sum = sum(member_usage.values())
        if len(members) == 1:
            allocation[members[0].id] = total_amount
        elif usage_sum > 0:
            assigned = 0
            for w in members[:-1]:
                share = int(round(total_amount * member_usage[w.id] / usage_sum))
                allocation[w.id] = share
                assigned += share
            allocation[members[-1].id] = total_amount - assigned
        else:
            share = total_amount // len(members) if members else 0
            for w in members[:-1]:
                allocation[w.id] = share
            if members:
                allocation[members[-1].id] = total_amount - share * (len(members) - 1)

    wbs_results: list[WbsResult] = []
    for wbs in data.wbs_list:
        wbs_amounts = {
            key: amounts[(wbs.id, key)]
            for key in (i.value for i in ItemType)
            if (wbs.id, key) in amounts
        }
        time_amount = wbs_amounts.get(ItemType.TIME.value, 0)
        expense_amount = wbs_amounts.get(ItemType.EXPENSE.value, 0)
        os_amount = wbs_amounts.get(ItemType.OS.value, 0)
        cumulative_usage = time_amount + expense_amount + os_amount

        billing_plans = billing_by_wbs.get(wbs.id, [])
        billing_from_records = wbs_amounts.get(ItemType.BILLING.value, 0)
        billed_from_plans = sum(p.billed_amount for p in billing_plans)
        billing_amount = max(billing_from_records, billed_from_plans)
        # Billing 계획이 등록돼 있으면 계획액을 그대로 쓴다(0으로 입력된 경우 포함).
        # 계획이 아예 없을 때만 실적 청구액으로 대체한다.
        planned_billing = (
            sum(p.planned_amount for p in billing_plans) if billing_plans else billing_amount
        )
        unbilled = (
            sum(p.unbilled for p in billing_plans)
            if billing_plans
            else max(0, cumulative_usage - billing_amount)
        )

        current_wip = time_amount + expense_amount - billing_amount
        screen_wip = wbs_amounts.get(ItemType.WIP.value)
        wip_mismatch = None if screen_wip is None else current_wip - screen_wip
        wbs_warnings: list[str] = []
        if wip_mismatch not in (None, 0):
            wbs_warnings.append(
                f"산식 WIP {current_wip:,}원과 화면 WIP {screen_wip:,}원의 차이 "
                f"{wip_mismatch:,}원 — 원본 확인이 필요합니다."
            )

        plans = staffing_by_wbs.get(wbs.id, [])
        backlog_entered = bool(plans)
        remaining_mm = sum(p.remaining_mm for p in plans)
        expected_time = sum(p.time_amount for p in plans)
        expected_other = int(data.expected_expense_os.get(wbs.id, 0))
        remaining_estimate = expected_time + expected_other

        eac = cumulative_usage + remaining_estimate
        allocated = allocation.get(wbs.id, 0)
        ltd_required = max(0, eac - allocated)
        ltd_adjusted = ltd_by_wbs.get(wbs.id, 0)
        if not backlog_entered:
            wbs_warnings.append("Backlog 미입력 — 종료예상값은 잠정치입니다(§FR-10).")

        wbs_results.append(
            WbsResult(
                wbs_id=wbs.id,
                code=wbs.code,
                contract_seq=wbs.contract_seq,
                amounts=wbs_amounts,
                cumulative_usage=cumulative_usage,
                billing=billing_amount,
                current_wip=current_wip,
                screen_wip=screen_wip,
                wip_mismatch=wip_mismatch,
                remaining_mm=remaining_mm,
                remaining_input_estimate=remaining_estimate,
                backlog_entered=backlog_entered,
                eac=eac,
                allocated_contract_amount=allocated,
                final_expected_balance=allocated - eac,
                expected_end_wip=eac - planned_billing,
                ltd_required=ltd_required,
                ltd_adjusted=ltd_adjusted,
                ltd_outstanding=max(0, ltd_required - ltd_adjusted),
                unbilled_amount=unbilled,
                warnings=wbs_warnings,
            )
        )

    results_by_wbs = {r.wbs_id: r for r in wbs_results}
    contract_results: list[ContractResult] = []
    for contract in sorted(data.contracts, key=lambda c: c.seq):
        members = wbs_by_contract.get(contract.id, [])
        member_results = [results_by_wbs[w.id] for w in members if w.id in results_by_wbs]
        usage = sum(r.cumulative_usage for r in member_results)
        eac = sum(r.eac for r in member_results)
        adjusted = sum(r.ltd_adjusted for r in member_results)
        required = max(0, eac - contract.amount)
        contract_results.append(
            ContractResult(
                contract_id=contract.id,
                seq=contract.seq,
                amount=contract.amount,
                cumulative_usage=usage,
                eac=eac,
                balance=contract.amount - usage,
                final_expected_balance=contract.amount - eac,
                ltd_required=required,
                ltd_adjusted=adjusted,
                ltd_outstanding=max(0, required - adjusted),
                wbs_ids=[r.wbs_id for r in member_results],
            )
        )

    total_contract = sum(c.amount for c in data.contracts)
    cumulative_usage = sum(r.cumulative_usage for r in wbs_results)
    total_billing = sum(r.billing for r in wbs_results)
    total_planned_billing = (
        sum(p.planned_amount for p in data.billing) if data.billing else total_billing
    )
    remaining_estimate = sum(r.remaining_input_estimate for r in wbs_results)
    backlog_entered = any(r.backlog_entered for r in wbs_results)
    eac = cumulative_usage + remaining_estimate
    current_wip = sum(r.current_wip for r in wbs_results)
    screen_wip_values = [r.screen_wip for r in wbs_results if r.screen_wip is not None]
    screen_wip = sum(screen_wip_values) if screen_wip_values else None
    wip_mismatch = None if screen_wip is None else current_wip - screen_wip

    # LTD 필요액은 차수별 초과분의 합으로 집계한다. 차수 간 잔액으로 상계하지 않는다.
    ltd_required = sum(c.ltd_required for c in contract_results)
    ltd_adjusted = sum(r.ltd_adjusted for r in wbs_results)

    plans = data.staffing
    total_remaining_mm = sum(p.remaining_mm for p in plans)
    weighted_rate: int | None = None
    if total_remaining_mm > 0:
        weighted_rate = int(
            round(sum(p.remaining_mm * p.rate for p in plans) / total_remaining_mm)
        )
    excess = max(0, eac - total_contract)
    required_mm = None
    if excess > 0 and weighted_rate:
        required_mm = round(excess / weighted_rate, 2)
    elif excess > 0:
        warnings.append(
            "잔여 인력 Rate 정보가 없어 절감 필요 MM을 계산할 수 없습니다. Backlog 화면을 등록하십시오."
        )

    if not backlog_entered:
        warnings.append(
            "Backlog 미입력 — 잔여 투입 예상액을 0으로 두지 않고 미입력으로 표시하며 "
            "종료예상값은 잠정치입니다(§FR-10)."
        )
    if wip_mismatch not in (None, 0):
        warnings.append(
            f"화면 WIP 합계와 산식 결과의 차이 {wip_mismatch:,}원 — 자동 확정을 보류합니다(§9)."
        )

    return EngagementPnl(
        engagement_id=data.engagement_id,
        formula_version=FORMULA_VERSION,
        snapshot_id=data.snapshot_id,
        total_contract_amount=total_contract,
        cumulative_usage=cumulative_usage,
        total_billing=total_billing,
        current_wip=current_wip,
        screen_wip=screen_wip,
        wip_mismatch=wip_mismatch,
        contract_balance=total_contract - cumulative_usage,
        remaining_input_estimate=remaining_estimate,
        backlog_entered=backlog_entered,
        provisional=not backlog_entered,
        eac=eac,
        final_expected_balance=total_contract - eac,
        expected_end_wip=eac - total_planned_billing,
        ltd_required=ltd_required,
        ltd_adjusted=ltd_adjusted,
        ltd_outstanding=max(0, ltd_required - ltd_adjusted),
        additional_contract_needed=excess,
        required_mm_reduction=required_mm,
        weighted_average_rate=weighted_rate,
        expected_margin_rate=(
            round((total_contract - eac) / total_contract, 6) if total_contract else None
        ),
        unbilled_amount=sum(r.unbilled_amount for r in wbs_results),
        contracts=contract_results,
        wbs_results=wbs_results,
        warnings=warnings,
    )
