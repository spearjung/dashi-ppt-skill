"""시나리오 계산기(§FR-11).

변수
  remaining_mm_delta_pct    잔여 MM 증감률(%)
  rate_override             적용 Rate(원/MM). 지정 시 모든 잔여 인력에 일괄 적용
  end_date_extension_months 종료일 연장 개월
  additional_contract_amount 추가계약 성사 금액
  expected_expense_os       잔여 기간 예상 Expense·OS 총액

종료일 연장은 '현재 월별 투입 수준이 연장 기간에도 유지된다'고 가정해
연장 개월 × (잔여 MM ÷ 계획 개월 수) 만큼 잔여 MM을 추가한다.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field, replace

from ..enums import ScenarioKind
from .formulas import EngagementPnl, PnlInput, StaffingInput, compute_pnl


@dataclass(slots=True)
class ScenarioParams:
    remaining_mm_delta_pct: float = 0.0
    rate_override: int | None = None
    end_date_extension_months: int = 0
    additional_contract_amount: int = 0
    expected_expense_os: int | None = None

    @classmethod
    def from_dict(cls, data: dict | None) -> "ScenarioParams":
        data = data or {}
        known = {f for f in cls.__slots__}
        return cls(**{k: v for k, v in data.items() if k in known and v is not None})

    def as_dict(self) -> dict:
        return asdict(self)


#: Base·Best·Worst 기본 변수값
SCENARIO_DEFAULTS: dict[str, ScenarioParams] = {
    ScenarioKind.BASE.value: ScenarioParams(),
    ScenarioKind.BEST.value: ScenarioParams(remaining_mm_delta_pct=-10.0),
    ScenarioKind.WORST.value: ScenarioParams(
        remaining_mm_delta_pct=20.0, end_date_extension_months=1
    ),
}


@dataclass(slots=True)
class ScenarioResult:
    kind: str
    params: dict
    expected_end_wip: int
    ltd_required: int
    additional_contract_needed: int
    required_mm_reduction: float | None
    expected_margin_rate: float | None
    eac: int
    final_expected_balance: int
    total_contract_amount: int
    remaining_input_estimate: int
    provisional: bool
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return asdict(self)


def _apply_params(data: PnlInput, params: ScenarioParams) -> PnlInput:
    """시나리오 변수를 손익 계산 입력에 반영한 새 입력을 만든다."""
    scoped = deepcopy(data)

    months = {p.month for p in scoped.staffing if p.month}
    plan_months = max(1, len(months))
    factor = 1.0 + params.remaining_mm_delta_pct / 100.0
    extension_factor = 1.0 + (params.end_date_extension_months / plan_months)

    staffing: list[StaffingInput] = []
    for plan in scoped.staffing:
        rate = params.rate_override if params.rate_override else plan.rate
        remaining = plan.remaining_mm * factor * extension_factor
        staffing.append(
            replace(
                plan,
                remaining_mm=round(remaining, 4),
                rate=rate,
                expected_time=None,  # MM × Rate 로 재계산
            )
        )
    scoped.staffing = staffing

    if params.expected_expense_os is not None:
        scoped.expected_expense_os = _spread(
            params.expected_expense_os, [w.id for w in scoped.wbs_list]
        )

    if params.additional_contract_amount:
        # 추가계약은 마지막 차수 금액에 가산한다. 차수가 없으면 무시한다.
        if scoped.contracts:
            last = max(scoped.contracts, key=lambda c: c.seq)
            last.amount += int(params.additional_contract_amount)
    return scoped


def _spread(total: int, wbs_ids: list[int]) -> dict[int, int]:
    """예상 Expense·OS 총액을 마지막 차수 WBS에 배정한다."""
    if not wbs_ids:
        return {}
    return {wbs_ids[-1]: int(total)}


def compute_scenario(data: PnlInput, kind: str, params: ScenarioParams | None = None) -> ScenarioResult:
    resolved = params or SCENARIO_DEFAULTS.get(kind, ScenarioParams())
    pnl: EngagementPnl = compute_pnl(_apply_params(data, resolved))
    return ScenarioResult(
        kind=kind,
        params=resolved.as_dict(),
        expected_end_wip=pnl.expected_end_wip,
        ltd_required=pnl.ltd_required,
        additional_contract_needed=pnl.additional_contract_needed,
        required_mm_reduction=pnl.required_mm_reduction,
        expected_margin_rate=pnl.expected_margin_rate,
        eac=pnl.eac,
        final_expected_balance=pnl.final_expected_balance,
        total_contract_amount=pnl.total_contract_amount,
        remaining_input_estimate=pnl.remaining_input_estimate,
        provisional=pnl.provisional,
        warnings=pnl.warnings,
    )


def compute_scenarios(
    data: PnlInput, params_by_kind: dict[str, ScenarioParams] | None = None
) -> list[ScenarioResult]:
    """Base·Best·Worst 3종을 동시에 계산한다."""
    overrides = params_by_kind or {}
    return [
        compute_scenario(data, kind, overrides.get(kind, SCENARIO_DEFAULTS[kind]))
        for kind in (ScenarioKind.BASE.value, ScenarioKind.BEST.value, ScenarioKind.WORST.value)
    ]
