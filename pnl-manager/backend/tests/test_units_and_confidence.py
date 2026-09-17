"""단위 인식·정규화(§FR-03, §9)와 신뢰도 등급(§FR-04) 검증."""

from __future__ import annotations

import pytest

from app.enums import Confidence
from app.ocr.confidence import (
    HIGH_IMPACT_ITEM_TYPES,
    blocks_confirmation,
    grade_row_field,
    is_high_impact,
    requires_individual_confirmation,
)
from app.ocr.units import (
    UnitParseError,
    detect_unit,
    format_krw,
    is_truncated,
    normalize_amount,
    parse_number,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Work In Progress (단위: 원)", "KRW"),
        ("WIP 조회 (단위: 천원)", "KRW_THOUSAND"),
        ("금액(백만원)", "KRW_MILLION"),
        ("Amount in thousands", "KRW_THOUSAND"),
        ("Billing Summary", None),  # 단위 미표시 → None
        (None, None),
    ],
)
def test_detect_unit(text, expected):
    assert detect_unit(text) == expected


@pytest.mark.parametrize(
    ("raw", "unit", "expected"),
    [
        ("263,746,000", "KRW", 263_746_000),
        ("8,030", "KRW_THOUSAND", 8_030_000),
        ("12.5", "KRW_MILLION", 12_500_000),
        (9_895_867, None, 9_895_867),  # 단위 미표시는 원 단위로 취급
        ("(1,234)", "KRW", -1_234),
    ],
)
def test_normalize_amount(raw, unit, expected):
    assert normalize_amount(raw, unit) == expected


@pytest.mark.parametrize("raw", ["1,23…", "12##", "", None, "abc", "1.2.3"])
def test_parse_number_rejects_unreliable_values(raw):
    with pytest.raises(UnitParseError):
        parse_number(raw)


def test_is_truncated():
    assert is_truncated("1,23…")
    assert is_truncated("123...")
    assert not is_truncated("1,234")


def test_format_krw():
    assert format_krw(9_895_867) == "9,895,867원"
    assert format_krw(None) == "-"


def test_high_impact_fields_match_prd():
    """§FR-04 고영향 필드 목록."""
    assert HIGH_IMPACT_ITEM_TYPES == frozenset(
        {"contract_amount", "time", "expense", "billing", "ltd"}
    )
    assert is_high_impact("time")
    assert not is_high_impact("provision")


def test_grade_high_when_clean():
    grade = grade_row_field(
        declared="high",
        item_type="time",
        amount_raw="263,746,000",
        unit="KRW",
        arithmetic_passed=True,
    )
    assert grade.confidence is Confidence.HIGH
    assert grade.reason is None


def test_grade_low_when_unit_missing():
    """단위 불명확 → Low(수정 또는 제외 필수)."""
    grade = grade_row_field(
        declared="high", item_type="time", amount_raw="8,030", unit=None
    )
    assert grade.confidence is Confidence.LOW
    assert "단위" in grade.reason
    assert blocks_confirmation(grade.confidence.value)


def test_grade_low_when_truncated():
    grade = grade_row_field(
        declared="high", item_type="expense", amount_raw="1,86…", unit="KRW", truncated=True
    )
    assert grade.confidence is Confidence.LOW
    assert "잘림" in grade.reason


def test_grade_medium_on_arithmetic_or_snapshot_mismatch():
    """판독은 되지만 합계·이전 Snapshot과 불일치 → Medium(개별 확인 필수)."""
    arithmetic = grade_row_field(
        declared="high", item_type="time", amount_raw="1", unit="KRW", arithmetic_passed=False
    )
    assert arithmetic.confidence is Confidence.MEDIUM
    snapshot = grade_row_field(
        declared="high", item_type="time", amount_raw="1", unit="KRW", snapshot_mismatch=True
    )
    assert snapshot.confidence is Confidence.MEDIUM
    assert requires_individual_confirmation("provision", Confidence.MEDIUM.value)


def test_grade_failed_when_unreadable():
    grade = grade_row_field(
        declared="high", item_type="time", amount_raw=None, unit="KRW", parse_failed=True
    )
    assert grade.confidence is Confidence.FAILED
    assert blocks_confirmation(grade.confidence.value)


def test_obstructed_value_downgraded():
    grade = grade_row_field(
        declared="high", item_type="billing", amount_raw="1,000", unit="KRW", obstructed=True
    )
    assert grade.confidence is Confidence.LOW
    assert "가림" in grade.reason


def test_batch_confirmation_only_for_non_high_impact_high():
    """일괄 확인은 고영향이 아닌 High 필드에만 허용된다(§FR-04)."""
    assert not requires_individual_confirmation("provision", Confidence.HIGH.value)
    assert requires_individual_confirmation("time", Confidence.HIGH.value)
    assert requires_individual_confirmation("provision", Confidence.LOW.value)


def test_backlog_mm_not_penalised_for_missing_currency_unit():
    """MM은 금액이 아니므로 단위 미표시로 강등하지 않는다."""
    grade = grade_row_field(
        declared="high", item_type="backlog_mm", amount_raw="3.5", unit=None
    )
    assert grade.confidence is Confidence.HIGH


def test_provider_registry_and_offline_default():
    """오프라인 기본값(manual)은 판독 없이 직접 입력 대기 상태를 만든다(§9)."""
    from pathlib import Path

    from app.ocr.providers import FixtureProvider, ManualProvider, get_provider

    assert isinstance(get_provider("manual"), ManualProvider)
    assert isinstance(get_provider("fixture"), FixtureProvider)
    with pytest.raises(ValueError):
        get_provider("unknown-engine")

    payload = ManualProvider().read(Path("/nonexistent.png"), screen_type="wip")
    assert payload.rows == []
    assert payload.screen_type.value == "wip"
    assert any("직접 입력" in w for w in payload.quality_warnings)


def test_fixture_provider_reads_sidecar(tmp_path):
    import json

    from app.ocr.providers import FixtureProvider

    image = tmp_path / "cap.png"
    image.write_bytes(b"x")
    (tmp_path / "cap.png.ocr.json").write_text(
        json.dumps({"screen_type": "wip", "rows": []}), encoding="utf-8"
    )
    payload = FixtureProvider().read(image)
    assert payload.screen_type.value == "wip"


def test_ocr_schema_rejects_free_text():
    """정의된 스키마를 벗어난 자유 텍스트 필드는 거부한다(§FR-03)."""
    from pydantic import ValidationError

    from app.ocr.schema import OcrPayload

    with pytest.raises(ValidationError):
        OcrPayload.model_validate({"screen_type": "wip", "rows": [], "commentary": "임의 설명"})
    with pytest.raises(ValidationError):
        OcrPayload.model_validate({"screen_type": "not_a_screen", "rows": []})


def test_screen_classifier_prefers_user_choice():
    from app.ocr.classifier import classify

    assert classify(user_choice="billing", screen_title="Work In Progress") == (
        __import__("app.enums", fromlist=["ScreenType"]).ScreenType.BILLING,
        "user",
    )
    screen, source = classify(screen_title="Work In Progress 조회")
    assert screen.value == "wip" and source == "title"
    screen, source = classify(filename="backlog-2025.png")
    assert screen.value == "backlog" and source == "filename"
    screen, source = classify()
    assert screen.value == "other" and source == "default"
