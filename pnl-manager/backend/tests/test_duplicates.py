"""중복 판정 5개 상황(§FR-07)."""

from __future__ import annotations

from datetime import date

from app.enums import DuplicateVerdict
from app.rules.duplicates import (
    DUPLICATE_KEY_FIELDS,
    RecordKey,
    find_intra_payload_duplicates,
    judge_duplicate,
)


def key(**overrides) -> RecordKey:
    base = dict(
        wbs_code="KOR01434-01-01",
        as_of_date=date(2025, 12, 31),
        period_from=date(2025, 5, 1),
        period_to=date(2025, 10, 31),
        item_type="time",
        amount=263_746_000,
        screen_title="Work In Progress",
        image_hash="a" * 64,
        value_basis="period",
    )
    base.update(overrides)
    return RecordKey(**base)


def test_eight_judgement_keys():
    """판정 Key 8종(§FR-07)."""
    assert DUPLICATE_KEY_FIELDS == (
        "wbs_code",
        "as_of_date",
        "period_from",
        "period_to",
        "item_type",
        "amount",
        "screen_title",
        "image_hash",
    )
    assert len(key().as_tuple()) == 8


def test_all_keys_identical_is_exact_duplicate():
    """Key 전체 동일 → 자동 중복 후보, 기본 제외·사용자 해제 가능."""
    decision = judge_duplicate(key(), [(1, key())])
    assert decision.verdict is DuplicateVerdict.EXACT_DUPLICATE
    assert decision.default_exclude is True
    assert decision.needs_user_choice is True
    assert decision.matched_record_id == 1


def test_same_wbs_same_period_different_amount_is_latest_snapshot_candidate():
    """동일 WBS·동일 기간·금액 상이 → 최신 Snapshot 후보, 대체 여부 선택."""
    decision = judge_duplicate(key(amount=300_000_000), [(7, key())])
    assert decision.verdict is DuplicateVerdict.LATEST_SNAPSHOT_CANDIDATE
    assert decision.needs_user_choice is True
    assert decision.default_exclude is False
    assert "대체" in decision.reason


def test_same_wbs_different_period_is_separate_snapshot():
    """동일 WBS·상이한 기간 → 별도 Snapshot, 자동 등록."""
    decision = judge_duplicate(
        key(period_from=date(2025, 11, 1), period_to=date(2025, 12, 31), amount=8_030_000),
        [(3, key())],
    )
    assert decision.verdict is DuplicateVerdict.SEPARATE_PERIOD
    assert decision.needs_user_choice is False
    assert decision.default_exclude is False


def test_cumulative_and_monthly_mix_is_basis_conflict():
    """누적값과 월 발생액 혼재 → 유형 분리, 합산 금지."""
    decision = judge_duplicate(
        key(value_basis="cumulative", amount=999),
        [(5, key(value_basis="monthly"))],
    )
    assert decision.verdict is DuplicateVerdict.BASIS_CONFLICT
    assert "합산하지 않고" in decision.reason


def test_change_link_for_before_after_screens():
    """수정 전·후 화면 → 변경 Snapshot, change_link로 연결."""
    decision = judge_duplicate(key(amount=1), [(9, key())], change_link_hint=True)
    assert decision.verdict is DuplicateVerdict.CHANGE_LINK
    assert decision.matched_record_id == 9


def test_new_record_when_no_match():
    decision = judge_duplicate(key(wbs_code="KOR01434-01-02"), [(1, key())])
    assert decision.verdict is DuplicateVerdict.NEW


def test_different_item_type_is_not_duplicate():
    decision = judge_duplicate(key(item_type="expense", amount=1), [(1, key())])
    assert decision.verdict is DuplicateVerdict.NEW


def test_intra_payload_duplicate_rows():
    """같은 업로드 안의 완전 동일 행 탐지(동일 화면 다중 업로드 방지)."""
    result = find_intra_payload_duplicates([(1, key()), (2, key()), (3, key(amount=5))])
    assert result == {2: 1}
