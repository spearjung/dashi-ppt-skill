"""중복 판정(§FR-07).

판정 Key 8종: WBS Code, 조회 기준일, 조회 시작일, 조회 종료일, 항목 유형,
금액, 화면 제목, 이미지 해시.

판정 결과
  Key 전체 동일            → exact_duplicate            (기본 제외, 사용자 해제 가능)
  동일 WBS·기간·금액 상이  → latest_snapshot_candidate  (이전 값 대체 여부 선택)
  동일 WBS·상이한 기간     → separate_period            (자동 등록)
  누적값·월 발생액 혼재    → basis_conflict             (유형 분리, 합산 금지)
  수정 전·후 화면          → change_link                (전·후 레코드 연결)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from ..enums import DuplicateVerdict

#: 판정 Key 8종의 필드명(감사·표시용)
DUPLICATE_KEY_FIELDS: tuple[str, ...] = (
    "wbs_code",
    "as_of_date",
    "period_from",
    "period_to",
    "item_type",
    "amount",
    "screen_title",
    "image_hash",
)


@dataclass(frozen=True, slots=True)
class RecordKey:
    """중복 판정 대상 레코드의 Key 8종."""

    wbs_code: str | None
    as_of_date: date | None
    period_from: date | None
    period_to: date | None
    item_type: str
    amount: int | None
    screen_title: str | None
    image_hash: str | None
    value_basis: str = "period"

    def as_tuple(self) -> tuple:
        return (
            self.wbs_code,
            self.as_of_date,
            self.period_from,
            self.period_to,
            self.item_type,
            self.amount,
            self.screen_title,
            self.image_hash,
        )

    @property
    def scope(self) -> tuple:
        """WBS·항목 유형 범위. 같은 범위 안에서만 기간·금액을 비교한다."""
        return (self.wbs_code, self.item_type)

    @property
    def period(self) -> tuple:
        return (self.period_from, self.period_to)


def duplicate_key(record: RecordKey) -> tuple:
    return record.as_tuple()


@dataclass(slots=True)
class DuplicateDecision:
    verdict: DuplicateVerdict
    matched_record_id: int | None = None
    reason: str | None = None
    #: 기본 제외 여부. exact_duplicate만 True.
    default_exclude: bool = False
    #: 사용자 선택이 필요한지
    needs_user_choice: bool = False

    def as_dict(self) -> dict:
        return {
            "verdict": self.verdict.value,
            "matched_record_id": self.matched_record_id,
            "reason": self.reason,
            "default_exclude": self.default_exclude,
            "needs_user_choice": self.needs_user_choice,
        }


def judge_duplicate(
    candidate: RecordKey,
    existing: list[tuple[int, RecordKey]],
    *,
    change_link_hint: bool = False,
) -> DuplicateDecision:
    """후보 레코드를 기존 확정 레코드 목록과 비교해 판정한다.

    existing 은 (record_id, RecordKey) 목록이며 확정 레코드만 전달한다.
    change_link_hint 는 사용자가 '수정 전·후 화면'이라고 표시한 경우 True.
    """
    same_scope = [(rid, key) for rid, key in existing if key.scope == candidate.scope]

    for rid, key in same_scope:
        if key.as_tuple() == candidate.as_tuple():
            return DuplicateDecision(
                verdict=DuplicateVerdict.EXACT_DUPLICATE,
                matched_record_id=rid,
                reason="판정 Key 8종이 모두 동일합니다.",
                default_exclude=True,
                needs_user_choice=True,
            )

    same_period = [(rid, key) for rid, key in same_scope if key.period == candidate.period]

    for rid, key in same_period:
        if key.value_basis != candidate.value_basis:
            return DuplicateDecision(
                verdict=DuplicateVerdict.BASIS_CONFLICT,
                matched_record_id=rid,
                reason=(
                    f"동일 기간에 값 기준이 다른 레코드가 있습니다"
                    f"({key.value_basis} vs {candidate.value_basis}). 합산하지 않고 분리 저장합니다."
                ),
                needs_user_choice=False,
            )

    if same_period:
        rid, key = same_period[0]
        if change_link_hint:
            return DuplicateDecision(
                verdict=DuplicateVerdict.CHANGE_LINK,
                matched_record_id=rid,
                reason="수정 전·후 화면으로 표시되어 전·후 레코드를 연결합니다.",
            )
        if key.amount != candidate.amount:
            return DuplicateDecision(
                verdict=DuplicateVerdict.LATEST_SNAPSHOT_CANDIDATE,
                matched_record_id=rid,
                reason=(
                    f"동일 WBS·동일 기간의 금액이 다릅니다"
                    f"(기존 {key.amount:,} → 판독 {candidate.amount:,}). 대체 여부를 선택하십시오."
                    if key.amount is not None and candidate.amount is not None
                    else "동일 WBS·동일 기간의 금액이 다릅니다. 대체 여부를 선택하십시오."
                ),
                needs_user_choice=True,
            )

    if same_scope:
        return DuplicateDecision(
            verdict=DuplicateVerdict.SEPARATE_PERIOD,
            reason="동일 WBS의 다른 기간 값으로 별도 등록합니다.",
        )

    return DuplicateDecision(verdict=DuplicateVerdict.NEW)


def find_intra_payload_duplicates(keys: list[tuple[int, RecordKey]]) -> dict[int, int]:
    """같은 업로드 안에서 완전히 동일한 행을 찾아 {중복행: 최초행} 으로 반환한다."""
    seen: dict[tuple, int] = {}
    result: dict[int, int] = {}
    for idx, key in keys:
        signature = key.as_tuple()
        if signature in seen:
            result[idx] = seen[signature]
        else:
            seen[signature] = idx
    return result
