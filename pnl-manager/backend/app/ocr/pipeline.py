"""판독 결과를 OcrRecord(임시 데이터)로 구조화한다(§FR-03 ~ §FR-07).

수행 순서
  1. 최초 판독값 원문을 Upload.ocr_payload에 불변 보존(§6.1)
  2. 단위 인식 후 금액을 원(KRW) 정수로 정규화(§9)
  3. 행 단위 레코드 분리 및 WBS Code 매칭
  4. 산술 교차검증(§FR-06)
  5. 이전 Snapshot·확정값 비교와 중복 판정(§FR-07)
  6. 필드별 신뢰도 부여(§FR-04)
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..enums import (
    NON_CURRENCY_ITEM_TYPES,
    CALCULABLE_ACTIONS,
    DuplicateVerdict,
    ScreenType,
    UploadStatus,
    ValueBasis,
)
from ..models import ConfirmedRecord, Contract, OcrRecord, Upload, Wbs
from ..rules.arithmetic import check_payload
from ..rules.duplicates import RecordKey, judge_duplicate
from .classifier import classify
from .confidence import grade_row_field, is_high_impact
from .providers import get_provider
from .schema import OcrPayload
from .units import UnitParseError, detect_unit, is_truncated, normalize_amount, parse_number

_NON_CURRENCY = {i.value for i in NON_CURRENCY_ITEM_TYPES}


def _engagement_wbs(session: Session, engagement_id: int) -> list[Wbs]:
    stmt = (
        select(Wbs)
        .join(Contract, Wbs.contract_id == Contract.id)
        .where(Contract.engagement_id == engagement_id)
        .order_by(Contract.seq, Wbs.code)
    )
    return list(session.execute(stmt).scalars())


def match_wbs(raw_code: str | None, wbs_list: list[Wbs]) -> Wbs | None:
    """판독된 WBS Code를 마스터에 매칭한다.

    화면 코드는 마스터보다 하위 레벨까지 표기되는 경우가 있어
    (예: 마스터 KOR01434-01-01 / 화면 KOR01434-01-01-01-1000)
    정확 일치 → 마스터가 화면 코드의 접두사 → 화면 코드가 마스터의 접두사 순으로 찾는다.
    """
    if not raw_code:
        return None
    code = raw_code.strip().upper()
    for wbs in wbs_list:
        if wbs.code.strip().upper() == code:
            return wbs
    prefixed = [w for w in wbs_list if code.startswith(w.code.strip().upper())]
    if prefixed:
        return max(prefixed, key=lambda w: len(w.code))
    reverse = [w for w in wbs_list if w.code.strip().upper().startswith(code)]
    if len(reverse) == 1:
        return reverse[0]
    return None


def _existing_keys(session: Session, engagement_id: int) -> list[tuple[int, RecordKey]]:
    """중복 판정 대상이 되는 기존 확정 레코드의 Key 8종."""
    stmt = select(ConfirmedRecord).where(
        ConfirmedRecord.engagement_id == engagement_id,
        ConfirmedRecord.action.in_([a.value for a in CALCULABLE_ACTIONS]),
    )
    keys: list[tuple[int, RecordKey]] = []
    for rec in session.execute(stmt).scalars():
        upload = session.get(Upload, rec.upload_id) if rec.upload_id else None
        keys.append(
            (
                rec.id,
                RecordKey(
                    wbs_code=rec.wbs.code if rec.wbs else None,
                    as_of_date=rec.as_of_date,
                    period_from=rec.period_from,
                    period_to=rec.period_to,
                    item_type=rec.item_type,
                    amount=rec.amount,
                    screen_title=upload.screen_title if upload else None,
                    image_hash=upload.image_hash if upload else None,
                    value_basis=rec.value_basis,
                ),
            )
        )
    return keys


def _baseline_amounts(session: Session, engagement_id: int) -> dict[tuple[int | None, str], int]:
    """단위 오류·Snapshot 비교용 기존 확정 금액."""
    stmt = select(ConfirmedRecord).where(
        ConfirmedRecord.engagement_id == engagement_id,
        ConfirmedRecord.action.in_([a.value for a in CALCULABLE_ACTIONS]),
    )
    out: dict[tuple[int | None, str], int] = {}
    for rec in session.execute(stmt).scalars():
        if rec.amount is None:
            continue
        key = (rec.wbs_id, rec.item_type)
        out[key] = out.get(key, 0) + rec.amount
    return out


def run_ocr(
    session: Session, upload: Upload, *, provider_name: str | None = None
) -> list[OcrRecord]:
    """업로드 이미지를 판독해 OcrRecord를 생성한다."""
    provider = get_provider(provider_name)
    wbs_list = _engagement_wbs(session, upload.engagement_id)
    payload = provider.read(
        Path(upload.file_path),
        screen_type=upload.screen_type if upload.screen_type_source == "user" else None,
        wbs_codes=[w.code for w in wbs_list],
    )
    upload.ocr_provider = provider.name
    return ingest_payload(session, upload, payload)


def ingest_payload(session: Session, upload: Upload, payload: OcrPayload) -> list[OcrRecord]:
    """판독 payload를 검증·정규화해 OcrRecord로 저장한다."""
    # 1) 최초 판독값 원문 보존
    upload.ocr_payload = payload.model_dump(mode="json", by_alias=True)

    # 화면 유형 확정(사용자 선택 우선)
    screen_type, source = classify(
        user_choice=upload.screen_type if upload.screen_type_source == "user" else None,
        payload_screen_type=payload.screen_type.value,
        screen_title=payload.screen_title,
        filename=upload.original_filename,
    )
    upload.screen_type = screen_type.value
    upload.screen_type_source = source
    upload.screen_title = payload.screen_title or upload.screen_title

    screen_unit = payload.unit or detect_unit(payload.screen_title)
    upload.unit = screen_unit
    upload.as_of_date = payload.as_of_date or upload.as_of_date

    wbs_list = _engagement_wbs(session, upload.engagement_id)
    existing_keys = _existing_keys(session, upload.engagement_id)
    baseline = _baseline_amounts(session, upload.engagement_id)

    # 기존 레코드 삭제 후 재판독 허용
    for old in list(upload.ocr_records):
        session.delete(old)
    session.flush()

    staged: list[dict] = []
    normalized_rows: list[dict] = []

    for row in payload.rows:
        wbs = match_wbs(row.wbs_code.value if row.wbs_code else None, wbs_list)
        row_period_from = row.period.from_ if row.period else (payload.period.from_ if payload.period else None)
        row_period_to = row.period.to if row.period else (payload.period.to if payload.period else None)
        row_as_of = row.as_of_date or payload.as_of_date
        row_basis = (row.value_basis or ValueBasis.PERIOD).value if row.value_basis else None

        amounts: dict[str, int] = {}
        for field_index, fld in enumerate(row.fields):
            unit = fld.unit or screen_unit
            item_type = fld.item_type.value
            basis = (
                fld.value_basis.value
                if fld.value_basis
                else row_basis or _default_basis(screen_type, row_period_from, row_period_to)
            )
            amount: int | None = None
            quantity: float | None = fld.quantity
            parse_failed = False
            truncated = is_truncated(str(fld.amount) if fld.amount is not None else None)

            if item_type in _NON_CURRENCY:
                if quantity is None and fld.amount is not None:
                    try:
                        quantity = parse_number(fld.amount)
                    except UnitParseError:
                        parse_failed = True
            elif fld.amount is not None:
                try:
                    amount = normalize_amount(fld.amount, unit)
                except UnitParseError:
                    parse_failed = True
            elif quantity is None:
                parse_failed = True

            if amount is not None:
                amounts[item_type] = amount

            staged.append(
                {
                    "row_index": row.row_index,
                    "field_index": field_index,
                    "wbs": wbs,
                    "wbs_code_raw": row.wbs_code.value if row.wbs_code else None,
                    "item_type": item_type,
                    "raw_label": fld.raw_label,
                    "amount_raw": None if fld.amount is None else str(fld.amount),
                    "amount": amount,
                    "quantity": quantity,
                    "unit": unit if item_type not in _NON_CURRENCY else None,
                    "value_basis": basis,
                    "period_from": row_period_from,
                    "period_to": row_period_to,
                    "as_of_date": row_as_of,
                    "declared": fld.confidence.value,
                    "parse_failed": parse_failed,
                    "truncated": truncated,
                    "obstructed": fld.obstructed,
                    "bbox": fld.bbox,
                    "note": fld.note,
                }
            )
        normalized_rows.append({"row_index": row.row_index, "amounts": amounts})

    # 2) 산술 교차검증
    totals: list[dict] = []
    for total in payload.totals:
        try:
            totals.append(
                {
                    "row_index": total.row_index,
                    "amount": normalize_amount(total.amount, screen_unit),
                }
            )
        except UnitParseError:
            continue
    checks = check_payload(normalized_rows, totals)
    upload.arithmetic_log = [c.as_dict() for c in checks]
    failed_rows = {c.row_index for c in checks if not c.passed}
    check_by_row: dict[int | None, dict] = {}
    for c in checks:
        if not c.passed or c.row_index not in check_by_row:
            check_by_row[c.row_index] = c.as_dict()

    # 3) 레코드 생성 + 중복 판정 + 신뢰도 부여
    records: list[OcrRecord] = []
    warnings: list[str] = list(payload.quality_warnings)
    for item in staged:
        wbs = item["wbs"]
        key = RecordKey(
            wbs_code=wbs.code if wbs else item["wbs_code_raw"],
            as_of_date=item["as_of_date"],
            period_from=item["period_from"],
            period_to=item["period_to"],
            item_type=item["item_type"],
            amount=item["amount"],
            screen_title=upload.screen_title,
            image_hash=upload.image_hash,
            value_basis=item["value_basis"],
        )
        decision = judge_duplicate(key, existing_keys)
        snapshot_mismatch = decision.verdict in (
            DuplicateVerdict.LATEST_SNAPSHOT_CANDIDATE,
            DuplicateVerdict.BASIS_CONFLICT,
        )
        if (
            item["value_basis"] == ValueBasis.CUMULATIVE.value
            and item["amount"] is not None
            and wbs is not None
        ):
            prior = baseline.get((wbs.id, item["item_type"]))
            if prior is not None and item["amount"] < prior:
                snapshot_mismatch = True

        arithmetic = check_by_row.get(item["row_index"])
        grade = grade_row_field(
            declared=item["declared"],
            item_type=item["item_type"],
            amount_raw=item["amount_raw"] if item["amount"] is not None or item["quantity"] is not None else None,
            unit=item["unit"] if item["item_type"] not in _NON_CURRENCY else "n/a",
            truncated=item["truncated"],
            parse_failed=item["parse_failed"],
            arithmetic_passed=None if arithmetic is None else arithmetic["passed"],
            snapshot_mismatch=snapshot_mismatch,
            obstructed=item["obstructed"],
        )
        if wbs is None and item["wbs_code_raw"]:
            warnings.append(
                f"WBS Code {item['wbs_code_raw']}를 프로젝트 마스터에서 찾지 못했습니다. "
                "검증 화면에서 WBS를 지정하십시오."
            )

        record = OcrRecord(
            row_index=item["row_index"],
            field_index=item["field_index"],
            wbs_code_raw=item["wbs_code_raw"],
            wbs_id=wbs.id if wbs else None,
            as_of_date=item["as_of_date"],
            period_from=item["period_from"],
            period_to=item["period_to"],
            item_type=item["item_type"],
            raw_label=item["raw_label"],
            amount_raw=item["amount_raw"],
            amount=item["amount"],
            quantity=item["quantity"],
            unit=item["unit"],
            value_basis=item["value_basis"],
            confidence=grade.confidence.value,
            confidence_reason=_merge_reason(grade.reason, item["note"], decision.reason),
            bbox=item["bbox"],
            arithmetic_check=arithmetic,
            duplicate_verdict=decision.verdict.value,
            duplicate_of_record_id=decision.matched_record_id,
            high_impact=is_high_impact(item["item_type"]),
        )
        # 관계를 통해 추가해 Upload.ocr_records 컬렉션이 즉시 최신 상태가 되게 한다.
        upload.ocr_records.append(record)
        records.append(record)

    if failed_rows:
        warnings.append(
            f"산술 교차검증 실패 행: {sorted(str(r) for r in failed_rows)} — 자동 확정을 보류합니다."
        )
    if not records:
        warnings.append("추출된 행이 없습니다. 캡처 품질 가이드를 확인하거나 값을 직접 입력하십시오.")

    upload.warnings = warnings
    upload.status = UploadStatus.OCR_DONE.value
    session.flush()
    return records


def _merge_reason(*parts: str | None) -> str | None:
    joined = "; ".join(p for p in parts if p)
    return joined or None


def _default_basis(screen_type: ScreenType, period_from: date | None, period_to: date | None) -> str:
    """값 기준 추정. 조회 기간이 명시되면 period, 아니면 누적으로 본다."""
    if period_from or period_to:
        return ValueBasis.PERIOD.value
    if screen_type in (ScreenType.WIP, ScreenType.BILLING, ScreenType.CONTRACT_INFO):
        return ValueBasis.CUMULATIVE.value
    return ValueBasis.PERIOD.value
