"""산술 교차검증(§FR-06).

확정 전에 화면 합계 검증·WIP 산식 검증·계약 잔액 검증을 자동 실행하고,
불일치 필드를 Medium으로 강등한다. 결과는 Upload별 로그로 보존한다.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from ..enums import ItemType

#: 원 단위 반올림 오차 허용치. 화면이 절사 표기하는 경우를 감안한다.
TOLERANCE_KRW = 1


@dataclass(slots=True)
class CheckResult:
    rule: str
    passed: bool
    diff: int = 0
    row_index: int | None = None
    message: str | None = None
    expected: int | None = None
    actual: int | None = None
    inputs: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return asdict(self)


def _passed(diff: int) -> bool:
    return abs(diff) <= TOLERANCE_KRW


def check_row_total(
    *, row_index: int, amounts: dict[str, int], screen_total: int | None
) -> CheckResult | None:
    """화면 합계 검증: Time + Expense + OS = 화면 합계."""
    if screen_total is None:
        return None
    parts = {
        key: amounts.get(key, 0)
        for key in (ItemType.TIME.value, ItemType.EXPENSE.value, ItemType.OS.value)
        if key in amounts
    }
    if not parts:
        return None
    computed = sum(parts.values())
    diff = computed - screen_total
    return CheckResult(
        rule="time+expense+os=total",
        passed=_passed(diff),
        diff=diff,
        row_index=row_index,
        expected=screen_total,
        actual=computed,
        inputs=parts,
        message=None
        if _passed(diff)
        else f"항목 합 {computed:,}원과 화면 합계 {screen_total:,}원의 차이 {diff:,}원",
    )


def check_wip_formula(
    *, row_index: int | None, time: int, expense: int, billing: int, screen_wip: int | None
) -> CheckResult | None:
    """현재 WIP 산식 검증: Time + Expense − Billing = 화면 WIP."""
    if screen_wip is None:
        return None
    computed = time + expense - billing
    diff = computed - screen_wip
    return CheckResult(
        rule="time+expense-billing=wip",
        passed=_passed(diff),
        diff=diff,
        row_index=row_index,
        expected=screen_wip,
        actual=computed,
        inputs={"time": time, "expense": expense, "billing": billing},
        message=None
        if _passed(diff)
        else f"산식 WIP {computed:,}원과 화면 WIP {screen_wip:,}원의 차이 {diff:,}원",
    )


def check_contract_balance(
    *, contract_amount: int, cumulative_usage: int, screen_balance: int | None
) -> CheckResult | None:
    """계약 대비 잔액 검증: 총 계약금액 − 누적 사용액 = 화면 잔액."""
    if screen_balance is None:
        return None
    computed = contract_amount - cumulative_usage
    diff = computed - screen_balance
    return CheckResult(
        rule="contract-usage=balance",
        passed=_passed(diff),
        diff=diff,
        expected=screen_balance,
        actual=computed,
        inputs={"contract_amount": contract_amount, "cumulative_usage": cumulative_usage},
        message=None
        if _passed(diff)
        else f"산식 잔액 {computed:,}원과 화면 잔액 {screen_balance:,}원의 차이 {diff:,}원",
    )


def check_payload(rows: list[dict], totals: list[dict]) -> list[CheckResult]:
    """정규화된 행 목록 전체에 대해 검증을 실행한다.

    rows 원소 형태: {"row_index": int, "amounts": {item_type: krw}}
    totals 원소 형태: {"row_index": int | None, "amount": krw}
    """
    results: list[CheckResult] = []
    by_row = {t.get("row_index"): t.get("amount") for t in totals}
    # 행이 하나뿐이고 합계에 row_index가 없으면 그 행의 합계로 간주한다.
    global_total = by_row.get(None)

    for row in rows:
        idx = row["row_index"]
        amounts = row["amounts"]
        screen_total = by_row.get(idx)
        if screen_total is None and len(rows) == 1:
            screen_total = global_total
        total_check = check_row_total(row_index=idx, amounts=amounts, screen_total=screen_total)
        if total_check:
            results.append(total_check)

        wip_check = check_wip_formula(
            row_index=idx,
            time=amounts.get(ItemType.TIME.value, 0),
            expense=amounts.get(ItemType.EXPENSE.value, 0),
            billing=amounts.get(ItemType.BILLING.value, 0),
            screen_wip=amounts.get(ItemType.WIP.value),
        )
        if wip_check:
            results.append(wip_check)

    # 여러 행이 있고 전체 합계 행이 별도로 있는 경우 행 합계의 총계를 검증한다.
    if global_total is not None and len(rows) > 1:
        computed = sum(
            amount
            for row in rows
            for key, amount in row["amounts"].items()
            if key in (ItemType.TIME.value, ItemType.EXPENSE.value, ItemType.OS.value)
        )
        diff = computed - global_total
        results.append(
            CheckResult(
                rule="sum(rows)=grand_total",
                passed=_passed(diff),
                diff=diff,
                expected=global_total,
                actual=computed,
                message=None
                if _passed(diff)
                else f"행 합계 {computed:,}원과 전체 합계 {global_total:,}원의 차이 {diff:,}원",
            )
        )
    return results


def failing_rows(results: list[CheckResult]) -> set[int | None]:
    """검증 실패한 row_index 집합. 해당 행 필드를 Medium으로 강등하는 데 사용한다."""
    return {r.row_index for r in results if not r.passed}
