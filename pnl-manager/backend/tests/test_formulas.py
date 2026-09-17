"""손익 산식(§3.2)과 시나리오(§FR-11) 검증."""

from __future__ import annotations

from datetime import date


from app.calc.formulas import (
    FORMULA_VERSION,
    BillingInput,
    ContractInput,
    CostRecord,
    LtdInput,
    PnlInput,
    StaffingInput,
    WbsInput,
    aggregate_amounts,
    compute_pnl,
)
from app.calc.scenario import ScenarioParams, compute_scenario, compute_scenarios

CONTRACT_AMOUNT = 100_000_000


def base_input(**overrides) -> PnlInput:
    data = dict(
        engagement_id=1,
        contract_type="fixed_price",
        contracts=[
            ContractInput(id=1, seq=0, amount=CONTRACT_AMOUNT,
                          valid_from=date(2025, 1, 1), valid_to=date(2025, 12, 31))
        ],
        wbs_list=[WbsInput(id=10, code="W-01", contract_id=1, contract_seq=0)],
        records=[
            CostRecord(10, "time", 60_000_000, period_from=date(2025, 1, 1),
                       period_to=date(2025, 6, 30)),
            CostRecord(10, "expense", 5_000_000, period_from=date(2025, 1, 1),
                       period_to=date(2025, 6, 30)),
            CostRecord(10, "os", 3_000_000, period_from=date(2025, 1, 1),
                       period_to=date(2025, 6, 30)),
        ],
    )
    data.update(overrides)
    return PnlInput(**data)


def test_formula_version_recorded():
    """계산 결과에 산식 버전이 함께 저장된다(§FR-10)."""
    assert compute_pnl(base_input()).formula_version == FORMULA_VERSION


def test_cumulative_usage_is_time_plus_expense_plus_os():
    pnl = compute_pnl(base_input())
    assert pnl.cumulative_usage == 68_000_000


def test_current_wip_is_time_plus_expense_minus_billing():
    """현재 WIP = Time + Expense − Billing."""
    data = base_input()
    data.records.append(
        CostRecord(10, "billing", 40_000_000, period_from=date(2025, 1, 1),
                   period_to=date(2025, 6, 30))
    )
    pnl = compute_pnl(data)
    assert pnl.current_wip == 60_000_000 + 5_000_000 - 40_000_000


def test_wip_mismatch_is_warned_not_silently_accepted():
    """화면 WIP와 산식 결과가 다르면 경고한다(§3.1, §9)."""
    data = base_input()
    data.records.append(CostRecord(10, "wip", 1_000_000))
    pnl = compute_pnl(data)
    assert pnl.screen_wip == 1_000_000
    assert pnl.wip_mismatch == 65_000_000 - 1_000_000
    assert any("WIP" in w for w in pnl.warnings)


def test_contract_balance():
    """계약 대비 잔액 = 총 계약금액 − 누적 사용액."""
    pnl = compute_pnl(base_input())
    assert pnl.contract_balance == CONTRACT_AMOUNT - 68_000_000


def test_remaining_estimate_and_eac_with_backlog():
    """잔여 투입 예상액 = Σ(잔여 MM × 적용 Rate) + 예상 Expense·OS, EAC = 누적 + 잔여."""
    data = base_input(
        staffing=[
            StaffingInput(wbs_id=10, remaining_mm=2.0, rate=10_000_000, month="2025-07"),
            StaffingInput(wbs_id=10, remaining_mm=1.5, rate=8_000_000, month="2025-08"),
        ],
        expected_expense_os={10: 2_000_000},
    )
    pnl = compute_pnl(data)
    assert pnl.remaining_input_estimate == 20_000_000 + 12_000_000 + 2_000_000
    assert pnl.eac == 68_000_000 + 34_000_000
    assert pnl.backlog_entered is True
    assert pnl.provisional is False


def test_backlog_missing_is_marked_provisional():
    """Backlog 미입력 시 0으로 두지 않고 잠정 처리한다(§FR-10)."""
    pnl = compute_pnl(base_input())
    assert pnl.backlog_entered is False
    assert pnl.provisional is True
    assert any("Backlog 미입력" in w for w in pnl.warnings)


def test_final_expected_balance_and_margin():
    """최종 예상 잔액 = 총 계약금액 − 종료예상 사용액, 예상 손익률 = 잔액 ÷ 계약금액."""
    data = base_input(
        staffing=[StaffingInput(wbs_id=10, remaining_mm=1.0, rate=10_000_000, month="2025-07")]
    )
    pnl = compute_pnl(data)
    assert pnl.eac == 78_000_000
    assert pnl.final_expected_balance == CONTRACT_AMOUNT - 78_000_000
    assert pnl.expected_margin_rate == round(22_000_000 / CONTRACT_AMOUNT, 6)


def test_loss_expected_when_balance_negative():
    data = base_input(
        staffing=[StaffingInput(wbs_id=10, remaining_mm=5.0, rate=10_000_000, month="2025-07")]
    )
    pnl = compute_pnl(data)
    assert pnl.eac == 118_000_000
    assert pnl.final_expected_balance < 0
    assert pnl.expected_margin_rate < 0


def test_ltd_required_is_zero_when_within_contract():
    """LTD 필요액 = max(0, 종료예상 사용액 − 총 계약금액)."""
    assert compute_pnl(base_input()).ltd_required == 0


def test_ltd_required_and_outstanding_with_adjustment():
    data = base_input(
        staffing=[StaffingInput(wbs_id=10, remaining_mm=5.0, rate=10_000_000, month="2025-07")],
        ltd_adjustments=[LtdInput(wbs_id=10, amount=5_000_000)],
    )
    pnl = compute_pnl(data)
    assert pnl.ltd_required == 18_000_000
    assert pnl.ltd_adjusted == 5_000_000
    assert pnl.ltd_outstanding == 13_000_000
    assert pnl.additional_contract_needed == 18_000_000


def test_required_mm_reduction_uses_weighted_average_rate():
    """절감 필요 MM = 초과분 ÷ 잔여 인력 가중평균 Rate."""
    data = base_input(
        staffing=[
            StaffingInput(wbs_id=10, remaining_mm=3.0, rate=10_000_000, month="2025-07"),
            StaffingInput(wbs_id=10, remaining_mm=1.0, rate=20_000_000, month="2025-08"),
        ]
    )
    pnl = compute_pnl(data)
    # 가중평균 Rate = (3×10M + 1×20M) / 4 = 12.5M
    assert pnl.weighted_average_rate == 12_500_000
    excess = pnl.eac - CONTRACT_AMOUNT
    assert pnl.required_mm_reduction == round(excess / 12_500_000, 2)


def test_required_mm_reduction_none_without_rate_info():
    data = base_input(
        records=base_input().records + [CostRecord(10, "time", 50_000_000,
                                                   period_from=date(2025, 7, 1),
                                                   period_to=date(2025, 8, 31))]
    )
    pnl = compute_pnl(data)
    assert pnl.additional_contract_needed > 0
    assert pnl.required_mm_reduction is None
    assert any("절감 필요 MM" in w for w in pnl.warnings)


def test_expected_end_wip_uses_planned_billing():
    """종료예상 WIP = 종료예상 사용액 − 총 Billing 예정액."""
    data = base_input(billing=[BillingInput(wbs_id=10, planned_amount=50_000_000,
                                            billed_amount=30_000_000)])
    pnl = compute_pnl(data)
    assert pnl.expected_end_wip == pnl.eac - 50_000_000
    assert pnl.unbilled_amount == 20_000_000


def test_cumulative_and_period_are_not_summed():
    """누적값과 기간 발생액을 혼합 합산하지 않는다(§3.1)."""
    records = [
        CostRecord(10, "time", 60_000_000, value_basis="cumulative", as_of_date=date(2025, 6, 30)),
        CostRecord(10, "time", 20_000_000, value_basis="period",
                   period_from=date(2025, 1, 1), period_to=date(2025, 3, 31)),
    ]
    amounts, _, warnings = aggregate_amounts(records)
    assert amounts[(10, "time")] == 60_000_000  # 누적값 채택
    assert any("합산 금지" in w for w in warnings)


def test_latest_cumulative_wins():
    records = [
        CostRecord(10, "time", 50_000_000, value_basis="cumulative", as_of_date=date(2025, 5, 31)),
        CostRecord(10, "time", 70_000_000, value_basis="cumulative", as_of_date=date(2025, 6, 30)),
    ]
    amounts, _, _ = aggregate_amounts(records)
    assert amounts[(10, "time")] == 70_000_000


def test_period_records_are_summed():
    """서로 다른 기간의 발생액은 합산한다."""
    records = [
        CostRecord(10, "time", 10_000_000, period_from=date(2025, 1, 1), period_to=date(2025, 3, 31)),
        CostRecord(10, "time", 20_000_000, period_from=date(2025, 4, 1), period_to=date(2025, 6, 30)),
    ]
    amounts, _, _ = aggregate_amounts(records)
    assert amounts[(10, "time")] == 30_000_000


def test_same_period_records_are_summed_after_reassignment():
    """재분류로 같은 기간 값이 한 WBS에 모이면 합산해야 한다(§12.2-4)."""
    records = [
        CostRecord(10, "time", 72_000_000, period_from=date(2025, 11, 1), period_to=date(2025, 12, 31)),
        CostRecord(10, "time", 8_030_000, period_from=date(2025, 11, 1), period_to=date(2025, 12, 31)),
    ]
    amounts, _, _ = aggregate_amounts(records)
    assert amounts[(10, "time")] == 80_030_000


def test_contract_amount_allocated_pro_rata_across_multiple_wbs():
    """한 차수에 WBS가 여러 개이면 계약금액을 사용액 비율로 배분한다."""
    data = base_input(
        wbs_list=[
            WbsInput(id=10, code="W-01", contract_id=1, contract_seq=0),
            WbsInput(id=11, code="W-02", contract_id=1, contract_seq=0),
        ],
        records=[
            CostRecord(10, "time", 30_000_000, period_from=date(2025, 1, 1)),
            CostRecord(11, "time", 10_000_000, period_from=date(2025, 1, 1)),
        ],
    )
    pnl = compute_pnl(data)
    allocated = {w.code: w.allocated_contract_amount for w in pnl.wbs_results}
    assert allocated["W-01"] == 75_000_000
    assert allocated["W-02"] == 25_000_000
    assert sum(allocated.values()) == CONTRACT_AMOUNT


def test_ltd_not_netted_across_contract_seq():
    """차수 간 잔액으로 초과분을 상계하지 않는다."""
    data = base_input(
        contracts=[
            ContractInput(id=1, seq=0, amount=50_000_000),
            ContractInput(id=2, seq=1, amount=50_000_000),
        ],
        wbs_list=[
            WbsInput(id=10, code="W-01", contract_id=1, contract_seq=0),
            WbsInput(id=20, code="W-02", contract_id=2, contract_seq=1),
        ],
        records=[
            CostRecord(10, "time", 80_000_000, period_from=date(2025, 1, 1)),
            CostRecord(20, "time", 10_000_000, period_from=date(2025, 7, 1)),
        ],
    )
    pnl = compute_pnl(data)
    assert pnl.ltd_required == 30_000_000  # 1차 초과분만
    assert pnl.contract_balance == 100_000_000 - 90_000_000


def test_scenarios_base_best_worst_computed_together():
    data = base_input(
        staffing=[StaffingInput(wbs_id=10, remaining_mm=4.0, rate=10_000_000, month="2025-07")]
    )
    results = compute_scenarios(data)
    kinds = [r.kind for r in results]
    assert kinds == ["base", "best", "worst"]
    base, best, worst = results
    assert best.eac < base.eac < worst.eac
    assert best.expected_margin_rate > base.expected_margin_rate > worst.expected_margin_rate


def test_scenario_additional_contract_reduces_ltd():
    data = base_input(
        staffing=[StaffingInput(wbs_id=10, remaining_mm=5.0, rate=10_000_000, month="2025-07")]
    )
    without = compute_scenario(data, "base", ScenarioParams())
    with_change_order = compute_scenario(
        data, "base", ScenarioParams(additional_contract_amount=18_000_000)
    )
    assert without.ltd_required == 18_000_000
    assert with_change_order.ltd_required == 0
    assert with_change_order.total_contract_amount == CONTRACT_AMOUNT + 18_000_000


def test_scenario_rate_override_and_mm_delta():
    data = base_input(
        staffing=[StaffingInput(wbs_id=10, remaining_mm=2.0, rate=10_000_000, month="2025-07")]
    )
    result = compute_scenario(
        data, "base", ScenarioParams(remaining_mm_delta_pct=50.0, rate_override=5_000_000)
    )
    assert result.remaining_input_estimate == int(2.0 * 1.5 * 5_000_000)


def test_scenario_end_date_extension_adds_months_of_staffing():
    """종료일 연장은 월별 투입 수준이 유지된다고 가정해 잔여 MM을 늘린다."""
    data = base_input(
        staffing=[
            StaffingInput(wbs_id=10, remaining_mm=1.0, rate=10_000_000, month="2025-07"),
            StaffingInput(wbs_id=10, remaining_mm=1.0, rate=10_000_000, month="2025-08"),
        ]
    )
    extended = compute_scenario(data, "base", ScenarioParams(end_date_extension_months=1))
    # 계획 2개월 → 1개월 연장 시 잔여 MM 1.5배
    assert extended.remaining_input_estimate == 30_000_000


def test_scenario_expected_expense_os_included():
    data = base_input(
        staffing=[StaffingInput(wbs_id=10, remaining_mm=1.0, rate=10_000_000, month="2025-07")]
    )
    result = compute_scenario(data, "base", ScenarioParams(expected_expense_os=3_000_000))
    assert result.remaining_input_estimate == 13_000_000


def test_scenario_does_not_mutate_input():
    data = base_input(
        staffing=[StaffingInput(wbs_id=10, remaining_mm=2.0, rate=10_000_000, month="2025-07")]
    )
    compute_scenario(data, "worst", ScenarioParams(remaining_mm_delta_pct=100.0,
                                                   additional_contract_amount=1_000))
    assert data.staffing[0].remaining_mm == 2.0
    assert data.contracts[0].amount == CONTRACT_AMOUNT
