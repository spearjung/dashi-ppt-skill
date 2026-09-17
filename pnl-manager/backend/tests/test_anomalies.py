"""이상징후 5종(§FR-09)."""

from __future__ import annotations

from datetime import date

from app.enums import IssueType
from app.rules.anomalies import (
    WBS_ATTRIBUTION_ACTIONS,
    EngagementView,
    RecordView,
    WbsView,
    detect_anomalies,
)

ENGAGEMENT = EngagementView(id=1, start_date=date(2025, 5, 1), end_date=date(2025, 12, 31))
WBS1 = WbsView(
    id=10,
    code="KOR01434-01-01",
    contract_seq=0,
    valid_from=date(2025, 5, 1),
    valid_to=date(2025, 10, 31),
)
WBS2 = WbsView(
    id=20,
    code="KOR01434-01-02",
    contract_seq=1,
    valid_from=date(2025, 11, 1),
    valid_to=date(2025, 12, 31),
)


def record(**overrides) -> RecordView:
    base = dict(
        id=1,
        wbs_id=10,
        wbs_code="KOR01434-01-01",
        item_type="time",
        amount=8_030_000,
        unit="KRW",
        period_from=date(2025, 5, 1),
        period_to=date(2025, 10, 31),
        as_of_date=date(2025, 12, 31),
    )
    base.update(overrides)
    return RecordView(**base)


def types(anomalies) -> set[str]:
    return {a.type.value for a in anomalies}


def test_wbs_attribution_error_groups_row_and_offers_four_actions():
    """1차 WBS 유효기간 이후 발생액 → 행 단위 Issue 1건, 제안 조치 4종."""
    rows = [
        record(id=1, item_type="time", amount=8_030_000,
               period_from=date(2025, 11, 1), period_to=date(2025, 12, 31)),
        record(id=2, item_type="expense", amount=1_865_867,
               period_from=date(2025, 11, 1), period_to=date(2025, 12, 31)),
    ]
    anomalies = detect_anomalies(engagement=ENGAGEMENT, records=rows, wbs_list=[WBS1, WBS2])
    attribution = [a for a in anomalies if a.type is IssueType.WBS_ATTRIBUTION]
    assert len(attribution) == 1
    issue = attribution[0]
    assert sorted(issue.related_record_ids) == [1, 2]
    assert issue.suggested_actions == WBS_ATTRIBUTION_ACTIONS
    assert len(issue.suggested_actions) == 4
    assert "9,895,867원" in issue.detail  # 행 합계
    assert "KOR01434-01-02" in issue.detail  # 재분류 대상 후보


def test_period_error_outside_contract_period():
    """조회 기간이 계약기간 밖."""
    rows = [record(period_from=date(2026, 1, 1), period_to=date(2026, 2, 28), wbs_id=20,
                   wbs_code="KOR01434-01-02")]
    anomalies = detect_anomalies(engagement=ENGAGEMENT, records=rows, wbs_list=[WBS1, WBS2])
    assert IssueType.PERIOD_ERROR.value in types(anomalies)
    period = next(a for a in anomalies if a.type is IssueType.PERIOD_ERROR)
    assert period.suggested_actions == ("confirm", "exclude")


def test_period_error_before_wbs_valid_from():
    """WBS 유효기간 시작 전 발생액도 기간 오류로 잡는다."""
    rows = [record(id=3, wbs_id=20, wbs_code="KOR01434-01-02",
                   period_from=date(2025, 5, 1), period_to=date(2025, 6, 30))]
    anomalies = detect_anomalies(engagement=ENGAGEMENT, records=rows, wbs_list=[WBS1, WBS2])
    assert IssueType.PERIOD_ERROR.value in types(anomalies)


def test_duplicate_anomaly_from_fr07_verdict():
    rows = [record(duplicate_verdict="exact_duplicate")]
    anomalies = detect_anomalies(engagement=ENGAGEMENT, records=rows, wbs_list=[WBS1])
    duplicate = next(a for a in anomalies if a.type is IssueType.DUPLICATE)
    assert duplicate.suggested_actions == ("exclude", "keep")

    rows = [record(duplicate_verdict="latest_snapshot_candidate")]
    anomalies = detect_anomalies(engagement=ENGAGEMENT, records=rows, wbs_list=[WBS1])
    candidate = next(a for a in anomalies if a.type is IssueType.DUPLICATE)
    assert candidate.suggested_actions == ("replace", "keep")


def test_unit_error_when_unit_missing():
    rows = [record(unit=None)]
    anomalies = detect_anomalies(engagement=ENGAGEMENT, records=rows, wbs_list=[WBS1])
    unit = next(a for a in anomalies if a.type is IssueType.UNIT_ERROR)
    assert "단위" in unit.title


def test_unit_error_on_magnitude_jump():
    """동일 WBS 항목 간 자릿수 급변(원 ↔ 천원 혼동)."""
    rows = [record(amount=263_746)]
    anomalies = detect_anomalies(
        engagement=ENGAGEMENT,
        records=rows,
        wbs_list=[WBS1],
        baseline_amounts={(10, "time"): 263_746_000},
    )
    unit = next(a for a in anomalies if a.type is IssueType.UNIT_ERROR)
    assert "자릿수" in unit.title


def test_no_unit_error_for_normal_growth():
    rows = [record(amount=300_000_000)]
    anomalies = detect_anomalies(
        engagement=ENGAGEMENT,
        records=rows,
        wbs_list=[WBS1],
        baseline_amounts={(10, "time"): 263_746_000},
    )
    assert IssueType.UNIT_ERROR.value not in types(anomalies)


def test_total_mismatch_anomaly():
    rows = [record(arithmetic_passed=False, arithmetic_message="차이 1,000원")]
    anomalies = detect_anomalies(engagement=ENGAGEMENT, records=rows, wbs_list=[WBS1])
    mismatch = next(a for a in anomalies if a.type is IssueType.TOTAL_MISMATCH)
    assert mismatch.detail == "차이 1,000원"
    assert mismatch.suggested_actions == ("recheck_source", "edit")


def test_clean_record_raises_nothing():
    anomalies = detect_anomalies(engagement=ENGAGEMENT, records=[record()], wbs_list=[WBS1])
    assert anomalies == []


def test_all_five_anomaly_types_covered():
    """§FR-09 표의 5종이 모두 탐지 가능하다."""
    rows = [
        record(id=1, item_type="time", amount=8_030_000,
               period_from=date(2025, 11, 1), period_to=date(2025, 12, 31)),
        record(id=2, wbs_id=20, wbs_code="KOR01434-01-02",
               period_from=date(2026, 3, 1), period_to=date(2026, 3, 31)),
        record(id=3, duplicate_verdict="exact_duplicate"),
        record(id=4, unit=None),
        record(id=5, arithmetic_passed=False),
    ]
    anomalies = detect_anomalies(engagement=ENGAGEMENT, records=rows, wbs_list=[WBS1, WBS2])
    assert types(anomalies) >= {
        IssueType.WBS_ATTRIBUTION.value,
        IssueType.PERIOD_ERROR.value,
        IssueType.DUPLICATE.value,
        IssueType.UNIT_ERROR.value,
        IssueType.TOTAL_MISMATCH.value,
    }
