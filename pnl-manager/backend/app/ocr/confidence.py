"""필드별 신뢰도 부여·확정 규칙(§FR-04).

등급
  High   명확하게 판독되고 산술검증 통과 → 일반 필드는 일괄 확인 가능
  Medium 판독 가능하나 다른 화면·이전 Snapshot과 불일치 → 개별 확인 필수
  Low    숫자 잘림 또는 단위 불명확 → 수정 또는 제외 필수
  Failed 판독 불가 → 직접 입력 필수
"""

from __future__ import annotations

from dataclasses import dataclass

from ..enums import Confidence, ItemType, NON_CURRENCY_ITEM_TYPES

#: 고영향 필드. High여도 개별 사용자 확인을 요구한다(§FR-04).
HIGH_IMPACT_ITEM_TYPES: frozenset[str] = frozenset(
    {
        ItemType.CONTRACT_AMOUNT.value,
        ItemType.TIME.value,
        ItemType.EXPENSE.value,
        ItemType.BILLING.value,
        ItemType.LTD.value,
    }
)

#: 항목 유형과 무관하게 고영향으로 다루는 속성(날짜·금액 단위·WBS Code)
HIGH_IMPACT_ATTRIBUTES: tuple[str, ...] = ("as_of_date", "period", "unit", "wbs_code")

HIGH_IMPACT_FIELDS = HIGH_IMPACT_ITEM_TYPES


@dataclass(slots=True)
class Grade:
    confidence: Confidence
    reason: str | None = None


def _downgrade(current: Confidence, target: Confidence) -> Confidence:
    from ..enums import CONFIDENCE_ORDER

    return target if CONFIDENCE_ORDER[target] < CONFIDENCE_ORDER[current] else current


def grade_row_field(
    *,
    declared: str | None,
    item_type: str,
    amount_raw: str | None,
    unit: str | None,
    truncated: bool = False,
    parse_failed: bool = False,
    arithmetic_passed: bool | None = None,
    cross_screen_mismatch: bool = False,
    snapshot_mismatch: bool = False,
    obstructed: bool = False,
) -> Grade:
    """단일 필드의 최종 신뢰도를 산출한다.

    판독기가 declared로 제시한 등급에서 시작해 강등만 적용한다. 강등 사유가
    여러 개인 경우 가장 낮은 등급을 채택하고 사유를 모두 기록한다.
    """
    reasons: list[str] = []
    try:
        level = Confidence(declared) if declared else Confidence.MEDIUM
    except ValueError:
        level = Confidence.MEDIUM
        reasons.append(f"판독기 등급 미인식({declared!r})")

    if parse_failed or amount_raw in (None, ""):
        level = _downgrade(level, Confidence.FAILED)
        reasons.append("판독 불가 — 직접 입력 필요")
    if truncated:
        level = _downgrade(level, Confidence.LOW)
        reasons.append("숫자 잘림 의심")
    if obstructed:
        level = _downgrade(level, Confidence.LOW)
        reasons.append("커서·팝업으로 숫자 가림")
    if unit is None and item_type not in {i.value for i in NON_CURRENCY_ITEM_TYPES}:
        level = _downgrade(level, Confidence.LOW)
        reasons.append("금액 단위 미표시")
    if arithmetic_passed is False:
        level = _downgrade(level, Confidence.MEDIUM)
        reasons.append("화면 합계와 불일치")
    if cross_screen_mismatch:
        level = _downgrade(level, Confidence.MEDIUM)
        reasons.append("다른 화면 값과 불일치")
    if snapshot_mismatch:
        level = _downgrade(level, Confidence.MEDIUM)
        reasons.append("이전 Snapshot과 불일치")

    return Grade(level, "; ".join(reasons) or None)


def is_high_impact(item_type: str) -> bool:
    return item_type in HIGH_IMPACT_ITEM_TYPES


def requires_individual_confirmation(item_type: str, confidence: str) -> bool:
    """개별 확인이 필요한 필드인지 판정한다.

    고영향 필드는 High여도 개별 확인이 필요하고, High가 아닌 모든 필드도
    개별 확인이 필요하다. 즉 일괄 확인은 '고영향이 아닌 High' 필드에만 허용된다.
    """
    if is_high_impact(item_type):
        return True
    return confidence != Confidence.HIGH.value


def blocks_confirmation(confidence: str) -> bool:
    """이 등급이 남아 있으면 최종 확정을 차단하는지(§FR-05)."""
    return confidence in (Confidence.FAILED.value, Confidence.LOW.value)
