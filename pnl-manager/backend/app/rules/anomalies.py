"""이상징후 탐지 5종(§FR-09).

  기간 오류     조회 기간이 계약기간·WBS 유효기간 밖        → 확인·제외
  WBS 귀속 오류 1차 WBS 유효기간 이후 발생액이 1차 WBS 귀속 → 유지·재분류·중복확인·임시제외
  중복          FR-07 판정                                   → 제외·유지
  단위 오류     동일 WBS 항목 간 자릿수 급변, 단위 미표시     → 단위 수정
  합계 불일치   FR-06 검증 실패                               → 원본 재확인·수정
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date

from ..enums import COST_ITEM_TYPES, DuplicateVerdict, IssueSeverity, IssueType

#: WBS 귀속 오류 제안 조치 4종(§FR-09, §12.2)
WBS_ATTRIBUTION_ACTIONS: tuple[str, ...] = (
    "keep_current_wbs",
    "reassign_to_next_wbs",
    "check_duplicate_input",
    "exclude_temporarily",
)

WBS_ATTRIBUTION_ACTION_LABELS: dict[str, str] = {
    "keep_current_wbs": "1차 WBS 유지",
    "reassign_to_next_wbs": "2차 WBS로 재분류",
    "check_duplicate_input": "중복 입력 여부 확인",
    "exclude_temporarily": "계산 대상에서 임시 제외",
}

#: 제안 조치 전체의 표시 라벨. 이상징후·조치사항 화면에서 공통으로 사용한다.
ACTION_LABELS: dict[str, str] = {
    **WBS_ATTRIBUTION_ACTION_LABELS,
    "confirm": "확인",
    "exclude": "제외",
    "keep": "유지",
    "replace": "최신 값으로 대체",
    "set_unit": "단위 수정",
    "recheck_source": "원본 재확인",
    "edit": "값 수정",
    "request_change_order": "추가계약 추진",
    "book_ltd": "LTD 상각 결정",
    "reduce_mm": "잔여 MM 절감",
    "issue_invoice": "청구 진행",
    "check_billing_plan": "Billing 일정 확인",
    "upload_backlog": "Backlog 화면 업로드",
    "enter_manually": "잔여 MM 직접 입력",
    "condition_cleared": "조건 해소(자동)",
}

#: 단위 오류 판정 기준. 동일 WBS·항목의 기존 금액 대비 자릿수 차이.
UNIT_MAGNITUDE_THRESHOLD = 3


@dataclass(slots=True)
class Anomaly:
    type: IssueType
    severity: IssueSeverity
    title: str
    detail: str
    suggested_actions: tuple[str, ...]
    related_record_ids: list[int] = field(default_factory=list)
    related_wbs_id: int | None = None
    dedup_key: str | None = None

    def as_dict(self) -> dict:
        return {
            "type": self.type.value,
            "severity": self.severity.value,
            "title": self.title,
            "detail": self.detail,
            "suggested_actions": list(self.suggested_actions),
            "related_record_ids": list(self.related_record_ids),
            "related_wbs_id": self.related_wbs_id,
            "dedup_key": self.dedup_key,
        }


@dataclass(slots=True)
class RecordView:
    """이상징후 판정에 필요한 레코드 요약."""

    id: int
    wbs_id: int | None
    wbs_code: str | None
    item_type: str
    amount: int | None
    unit: str | None
    period_from: date | None
    period_to: date | None
    as_of_date: date | None
    duplicate_verdict: str = DuplicateVerdict.NEW.value
    arithmetic_passed: bool | None = None
    arithmetic_message: str | None = None


@dataclass(slots=True)
class WbsView:
    id: int
    code: str
    contract_seq: int
    valid_from: date | None
    valid_to: date | None


@dataclass(slots=True)
class EngagementView:
    id: int
    start_date: date | None
    end_date: date | None


def _outside(
    period_from: date | None, period_to: date | None, valid_from: date | None, valid_to: date | None
) -> bool:
    """조회 기간이 유효기간을 벗어나는지. 경계 정보가 없으면 판정하지 않는다."""
    ref_start = period_from or period_to
    ref_end = period_to or period_from
    if ref_start is None or ref_end is None:
        return False
    if valid_to is not None and ref_start > valid_to:
        return True
    if valid_from is not None and ref_end < valid_from:
        return True
    return False


def _next_wbs(current: WbsView, all_wbs: list[WbsView], period_from: date | None) -> WbsView | None:
    """발생 기간을 포함하는 다음 차수 WBS를 찾는다."""
    candidates = [w for w in all_wbs if w.contract_seq > current.contract_seq]
    if period_from is not None:
        covering = [
            w
            for w in candidates
            if (w.valid_from is None or w.valid_from <= period_from)
            and (w.valid_to is None or w.valid_to >= period_from)
        ]
        if covering:
            return min(covering, key=lambda w: w.contract_seq)
    return min(candidates, key=lambda w: w.contract_seq) if candidates else None


def detect_anomalies(
    *,
    engagement: EngagementView,
    records: list[RecordView],
    wbs_list: list[WbsView],
    baseline_amounts: dict[tuple[int | None, str], int] | None = None,
) -> list[Anomaly]:
    """레코드 목록에서 이상징후를 탐지한다.

    기간 오류·WBS 귀속 오류는 화면의 한 행(동일 WBS·동일 조회 기간)을 단위로
    판정한다. 한 행의 Time·Expense·OS는 같은 발생액이므로 필드별로 쪼개지 않고
    행 단위 Issue 하나로 묶어 제안 조치를 적용한다.

    중복·단위 오류·합계 불일치는 필드 단위로 판정한다.

    baseline_amounts 는 단위 오류 판정을 위한 기존 확정값
    {(wbs_id, item_type): 금액} 이다.
    """
    wbs_by_id = {w.id: w for w in wbs_list}
    baseline = baseline_amounts or {}
    anomalies: list[Anomaly] = []
    cost_types = {i.value for i in COST_ITEM_TYPES}

    # ---- 행 단위 판정: 기간 오류·WBS 귀속 오류
    groups: dict[tuple[int, date | None, date | None], list[RecordView]] = {}
    grouped_ids: set[int] = set()
    for rec in records:
        if rec.item_type in cost_types and rec.wbs_id is not None:
            groups.setdefault((rec.wbs_id, rec.period_from, rec.period_to), []).append(rec)
            grouped_ids.add(rec.id)

    for (wbs_id, period_from, period_to), members in groups.items():
        wbs = wbs_by_id.get(wbs_id)
        if wbs is None:
            continue
        total = sum(m.amount or 0 for m in members)
        record_ids = [m.id for m in members]
        breakdown = ", ".join(f"{m.item_type} {(m.amount or 0):,}원" for m in members)
        reference = period_from or period_to

        outside_engagement = _outside(
            period_from, period_to, engagement.start_date, engagement.end_date
        )
        after_wbs_valid_to = (
            wbs.valid_to is not None and reference is not None and reference > wbs.valid_to
        )
        target = _next_wbs(wbs, wbs_list, period_from) if after_wbs_valid_to else None

        # 계약기간 자체를 벗어난 발생액은 옮길 곳이 없으므로 기간 오류로 본다.
        # 귀속 오류는 이 WBS 이후 차수의 WBS가 존재하는 경우에만 성립한다.
        if after_wbs_valid_to and not outside_engagement and target is not None:
            anomalies.append(
                Anomaly(
                    type=IssueType.WBS_ATTRIBUTION,
                    severity=IssueSeverity.HIGH,
                    title=f"{wbs.code} 유효기간 이후 발생액이 {wbs.code}에 귀속",
                    detail=(
                        f"조회 기간 {period_from} ~ {period_to}의 발생액 {total:,}원"
                        f"({breakdown})이 {wbs.code}의 유효기간 종료일({wbs.valid_to}) "
                        "이후에 발생했습니다."
                        + (f" 재분류 대상 후보: {target.code}" if target else "")
                    ),
                    suggested_actions=WBS_ATTRIBUTION_ACTIONS,
                    related_record_ids=record_ids,
                    related_wbs_id=wbs.id,
                    dedup_key=f"wbs_attribution:{wbs.id}:{period_from}:{period_to}",
                )
            )
            continue

        if outside_engagement:
            anomalies.append(
                Anomaly(
                    type=IssueType.PERIOD_ERROR,
                    severity=IssueSeverity.MEDIUM,
                    title="조회 기간이 계약기간 밖",
                    detail=(
                        f"조회 기간({period_from} ~ {period_to})이 계약기간"
                        f"({engagement.start_date} ~ {engagement.end_date}) 밖입니다. "
                        f"대상 발생액 {total:,}원({breakdown})."
                    ),
                    suggested_actions=("confirm", "exclude"),
                    related_record_ids=record_ids,
                    related_wbs_id=wbs.id,
                    dedup_key=f"period_error:{wbs.id}:{period_from}:{period_to}",
                )
            )
        elif after_wbs_valid_to or _outside(period_from, period_to, wbs.valid_from, wbs.valid_to):
            anomalies.append(
                Anomaly(
                    type=IssueType.PERIOD_ERROR,
                    severity=IssueSeverity.MEDIUM,
                    title=f"조회 기간이 {wbs.code} 유효기간 밖",
                    detail=(
                        f"조회 기간({period_from} ~ {period_to})이 {wbs.code} 유효기간"
                        f"({wbs.valid_from} ~ {wbs.valid_to}) 밖입니다. "
                        f"대상 발생액 {total:,}원({breakdown})."
                    ),
                    suggested_actions=("confirm", "exclude"),
                    related_record_ids=record_ids,
                    related_wbs_id=wbs.id,
                    dedup_key=f"period_error:{wbs.id}:{period_from}:{period_to}",
                )
            )

    # ---- 필드 단위 판정
    for rec in records:
        wbs = wbs_by_id.get(rec.wbs_id) if rec.wbs_id is not None else None

        # 행 단위로 이미 판정한 레코드는 기간 검사를 건너뛴다.
        if rec.id not in grouped_ids:
            if _outside(
                rec.period_from, rec.period_to, engagement.start_date, engagement.end_date
            ):
                anomalies.append(
                    Anomaly(
                        type=IssueType.PERIOD_ERROR,
                        severity=IssueSeverity.MEDIUM,
                        title="조회 기간이 계약기간 밖",
                        detail=(
                            f"조회 기간({rec.period_from} ~ {rec.period_to})이 계약기간"
                            f"({engagement.start_date} ~ {engagement.end_date}) 밖입니다."
                        ),
                        suggested_actions=("confirm", "exclude"),
                        related_record_ids=[rec.id],
                        related_wbs_id=rec.wbs_id,
                        dedup_key=f"period_error:record:{rec.id}",
                    )
                )
            elif wbs is not None and _outside(
                rec.period_from, rec.period_to, wbs.valid_from, wbs.valid_to
            ):
                anomalies.append(
                    Anomaly(
                        type=IssueType.PERIOD_ERROR,
                        severity=IssueSeverity.MEDIUM,
                        title=f"조회 기간이 {wbs.code} 유효기간 밖",
                        detail=(
                            f"조회 기간({rec.period_from} ~ {rec.period_to})이 {wbs.code} "
                            f"유효기간({wbs.valid_from} ~ {wbs.valid_to}) 밖입니다."
                        ),
                        suggested_actions=("confirm", "exclude"),
                        related_record_ids=[rec.id],
                        related_wbs_id=wbs.id,
                        dedup_key=f"period_error:record:{rec.id}",
                    )
                )

        # 중복
        if rec.duplicate_verdict in (
            DuplicateVerdict.EXACT_DUPLICATE.value,
            DuplicateVerdict.LATEST_SNAPSHOT_CANDIDATE.value,
        ):
            exact = rec.duplicate_verdict == DuplicateVerdict.EXACT_DUPLICATE.value
            anomalies.append(
                Anomaly(
                    type=IssueType.DUPLICATE,
                    severity=IssueSeverity.HIGH if exact else IssueSeverity.MEDIUM,
                    title="중복 의심" if exact else "최신 Snapshot 후보",
                    detail=(
                        f"{rec.wbs_code} {rec.item_type} {(rec.amount or 0):,}원이 "
                        + (
                            "기존 확정값과 판정 Key 8종 모두 동일합니다."
                            if exact
                            else "기존 확정값과 동일 기간·상이 금액입니다."
                        )
                    ),
                    suggested_actions=("exclude", "keep") if exact else ("replace", "keep"),
                    related_record_ids=[rec.id],
                    related_wbs_id=rec.wbs_id,
                    dedup_key=f"duplicate:{rec.id}",
                )
            )

        # 단위 오류 — 단위 미표시 또는 동일 WBS·항목 대비 자릿수 급변
        if rec.unit is None and rec.amount is not None:
            anomalies.append(
                Anomaly(
                    type=IssueType.UNIT_ERROR,
                    severity=IssueSeverity.MEDIUM,
                    title="금액 단위 미표시",
                    detail=f"{rec.wbs_code} {rec.item_type} 값의 금액 단위를 확인할 수 없습니다.",
                    suggested_actions=("set_unit", "exclude"),
                    related_record_ids=[rec.id],
                    related_wbs_id=rec.wbs_id,
                    dedup_key=f"unit_error:{rec.id}",
                )
            )
        else:
            prior = baseline.get((rec.wbs_id, rec.item_type))
            if prior and rec.amount and _magnitude_jump(prior, rec.amount):
                anomalies.append(
                    Anomaly(
                        type=IssueType.UNIT_ERROR,
                        severity=IssueSeverity.MEDIUM,
                        title="동일 항목 자릿수 급변",
                        detail=(
                            f"{rec.wbs_code} {rec.item_type}: 기존 {prior:,}원 → 판독 "
                            f"{rec.amount:,}원. 단위(원·천원·백만원) 혼동 여부를 확인하십시오."
                        ),
                        suggested_actions=("set_unit", "confirm", "exclude"),
                        related_record_ids=[rec.id],
                        related_wbs_id=rec.wbs_id,
                        dedup_key=f"unit_error:{rec.id}",
                    )
                )

        # 합계 불일치
        if rec.arithmetic_passed is False:
            anomalies.append(
                Anomaly(
                    type=IssueType.TOTAL_MISMATCH,
                    severity=IssueSeverity.HIGH,
                    title="화면 합계와 산식 결과 불일치",
                    detail=rec.arithmetic_message or "산술 교차검증에 실패했습니다.",
                    suggested_actions=("recheck_source", "edit"),
                    related_record_ids=[rec.id],
                    related_wbs_id=rec.wbs_id,
                    dedup_key=f"total_mismatch:{rec.id}",
                )
            )

    return anomalies


def _magnitude_jump(prior: int, current: int) -> bool:
    """자릿수 차이가 임계치 이상인지."""
    if prior == 0 or current == 0:
        return False
    ratio = abs(current) / abs(prior)
    if ratio == 0:
        return False
    return abs(math.log10(ratio)) >= UNIT_MAGNITUDE_THRESHOLD
