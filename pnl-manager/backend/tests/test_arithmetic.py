"""산술 교차검증(§FR-06)."""

from __future__ import annotations

from app.rules.arithmetic import (
    check_contract_balance,
    check_payload,
    check_row_total,
    check_wip_formula,
    failing_rows,
)


def test_row_total_passes():
    result = check_row_total(
        row_index=1,
        amounts={"time": 263_746_000, "expense": 6_216_247},
        screen_total=269_962_247,
    )
    assert result.passed is True
    assert result.diff == 0
    assert result.rule == "time+expense+os=total"


def test_row_total_includes_os():
    result = check_row_total(
        row_index=1,
        amounts={"time": 100, "expense": 200, "os": 300},
        screen_total=600,
    )
    assert result.passed is True


def test_row_total_failure_reports_difference():
    result = check_row_total(
        row_index=2, amounts={"time": 8_030_000, "expense": 1_865_867}, screen_total=9_000_000
    )
    assert result.passed is False
    assert result.diff == 895_867
    assert "895,867" in result.message


def test_no_check_without_screen_total():
    """화면 합계가 없으면 검증을 생성하지 않는다(임의 가정 금지)."""
    assert check_row_total(row_index=1, amounts={"time": 1}, screen_total=None) is None


def test_wip_formula_check():
    result = check_wip_formula(
        row_index=1, time=100, expense=50, billing=30, screen_wip=120
    )
    assert result.passed is True
    assert result.actual == 120

    mismatch = check_wip_formula(row_index=1, time=100, expense=50, billing=30, screen_wip=100)
    assert mismatch.passed is False
    assert mismatch.diff == 20


def test_contract_balance_check():
    result = check_contract_balance(
        contract_amount=238_000_000, cumulative_usage=269_962_247, screen_balance=-31_962_247
    )
    assert result.passed is True


def test_check_payload_multi_row_and_grand_total():
    rows = [
        {"row_index": 1, "amounts": {"time": 263_746_000, "expense": 6_216_247}},
        {"row_index": 2, "amounts": {"time": 8_030_000, "expense": 1_865_867}},
    ]
    totals = [
        {"row_index": 1, "amount": 269_962_247},
        {"row_index": 2, "amount": 9_895_867},
        {"row_index": None, "amount": 279_858_114},
    ]
    results = check_payload(rows, totals)
    assert all(r.passed for r in results)
    assert any(r.rule == "sum(rows)=grand_total" for r in results)
    assert failing_rows(results) == set()


def test_check_payload_detects_grand_total_mismatch():
    rows = [
        {"row_index": 1, "amounts": {"time": 100}},
        {"row_index": 2, "amounts": {"time": 200}},
    ]
    totals = [{"row_index": None, "amount": 500}]
    results = check_payload(rows, totals)
    grand = next(r for r in results if r.rule == "sum(rows)=grand_total")
    assert grand.passed is False
    assert grand.diff == -200


def test_single_row_uses_global_total():
    rows = [{"row_index": 1, "amounts": {"time": 100, "expense": 50}}]
    totals = [{"row_index": None, "amount": 150}]
    results = check_payload(rows, totals)
    assert results and results[0].passed is True


def test_tolerance_absorbs_one_won_rounding():
    result = check_row_total(row_index=1, amounts={"time": 100}, screen_total=101)
    assert result.passed is True
