"""데모 데이터 생성.

KOR01434 수용 기준 시나리오(§12)를 화면 캡처 이미지와 함께 만들어
UI를 실제 데이터로 확인할 수 있게 한다. 캡처 이미지는 사내 화면을 모사한
합성 이미지이며 실제 시스템 데이터를 포함하지 않는다.

    python scripts/seed_demo.py [--reset]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from app import config  # noqa: E402
from app.api.engagements import _add_contract  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.models import Base, Engagement  # noqa: E402
from app.ocr.pipeline import ingest_payload  # noqa: E402
from app.ocr.schema import OcrPayload  # noqa: E402
from app.schemas import ContractCreate, EngagementCreate  # noqa: E402
from app.services import issues as issues_service  # noqa: E402
from app.services import uploads as upload_service  # noqa: E402

ENGAGEMENT = {
    "name": "KOR01434 손익관리 고도화",
    "client": "가상 고객사",
    "engagement_code": "KOR01434",
    "contract_type": "fixed_price",
    "ep": "EP",
    "em": "EM",
    "start_date": "2025-05-01",
    "end_date": "2025-12-31",
    "currency": "KRW",
    "contracts": [
        {
            "seq": 0,
            "amount": 238_000_000,
            "valid_from": "2025-05-01",
            "valid_to": "2025-10-31",
            "wbs_list": [{"code": "KOR01434-01-01", "name": "1차 계약 WBS"}],
        },
        {
            "seq": 1,
            "amount": 50_000_000,
            "valid_from": "2025-11-01",
            "valid_to": "2025-12-31",
            "wbs_list": [{"code": "KOR01434-01-02", "name": "2차 변경계약 WBS"}],
        },
    ],
}

CAPTURES = [
    {
        "title": "Work In Progress (단위: 원)",
        "as_of": "2025-12-31",
        "columns": ["WBS Code", "Period", "Time", "Expense", "Total"],
        "rows": [
            ["KOR01434-01-01-01-1000", "2025-05 ~ 2025-10", "263,746,000", "6,216,247", "269,962,247"],
            ["KOR01434-01-01-01-1000", "2025-11 ~ 2025-12", "8,030,000", "1,865,867", "9,895,867"],
        ],
        "filename": "wip-wbs1.png",
    },
    {
        "title": "Work In Progress (단위: 원)",
        "as_of": "2025-12-31",
        "columns": ["WBS Code", "Period", "Time", "Expense", "Total"],
        "rows": [
            ["KOR01434-01-02-01-1000", "2025-11 ~ 2025-12", "72,000,000", "5,629,160", "77,629,160"],
            ["KOR01434-01-02-01-1000", "LTD Adjustment", "10,000,000", "Change Order", "50,000,000"],
        ],
        "filename": "wip-wbs2.png",
    },
]

#: 두 번째 데모 프로젝트. Backlog·Billing이 입력되어 있어 시나리오 계산기와
#: 다중 프로젝트 대시보드를 확인할 수 있다. KOR01434는 §12 수용 기준값을
#: 그대로 유지하기 위해 Backlog를 넣지 않는다.
ENGAGEMENT_2 = {
    "name": "KOR02201 데이터 플랫폼 구축",
    "client": "가상 제조사",
    "engagement_code": "KOR02201",
    "contract_type": "time_and_material",
    "ep": "EP",
    "em": "EM2",
    "start_date": "2026-01-01",
    "end_date": "2026-09-30",
    "currency": "KRW",
    "contracts": [
        {
            "seq": 0,
            "amount": 900_000_000,
            "valid_from": "2026-01-01",
            "valid_to": "2026-09-30",
            "wbs_list": [{"code": "KOR02201-01-01", "name": "구축 WBS"}],
        }
    ],
}

CAPTURE_2 = {
    "title": "Work In Progress (단위: 원)",
    "as_of": "2026-06-30",
    "columns": ["WBS Code", "Period", "Time", "Expense", "Total"],
    "rows": [
        ["KOR02201-01-01-01-1000", "2026-01 ~ 2026-06", "512,400,000", "18,340,000", "530,740,000"],
    ],
    "filename": "wip-kor02201.png",
}

#: 잔여 투입 계획(Backlog 화면 대체 입력). 2026-07 ~ 09 3개월.
STAFFING_2 = [
    {"month": "2026-07", "remaining_mm": 3.0, "rate": 28_000_000, "person_or_grade": "Consultant"},
    {"month": "2026-08", "remaining_mm": 3.0, "rate": 28_000_000, "person_or_grade": "Consultant"},
    {"month": "2026-09", "remaining_mm": 2.0, "rate": 32_000_000, "person_or_grade": "Manager"},
]

#: Billing 실적·예정
BILLING_2 = {"planned_amount": 600_000_000, "billed_amount": 480_000_000, "billing_date": "2026-06-30"}


ROW_TOP = 112
ROW_HEIGHT = 30
COL_X = [16, 250, 420, 560, 700]
COL_W = [230, 165, 135, 135, 140]
WIDTH = 860
HEIGHT = ROW_TOP + ROW_HEIGHT * 3 + 20

#: 한글 자모를 포함하는 폰트를 우선 사용한다. 없으면 라틴 폰트로 대체한다.
FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
)


def _font(size: int):
    for candidate in FONT_CANDIDATES:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def render_capture(spec: dict) -> bytes:
    """사내 조회 화면을 모사한 표 이미지를 만든다."""
    image = Image.new("RGB", (WIDTH, HEIGHT), "#ffffff")
    draw = ImageDraw.Draw(image)
    title_font, head_font, body_font = _font(16), _font(12), _font(13)

    draw.rectangle([0, 0, WIDTH, 44], fill="#eef4f1")
    draw.text((16, 13), spec["title"], fill="#006940", font=title_font)
    draw.text(
        (16, 56),
        f"As of: {spec['as_of']}    Filter: Engagement = KOR01434",
        fill="#5c5c5c",
        font=head_font,
    )

    header_y = ROW_TOP - ROW_HEIGHT
    draw.rectangle([8, header_y, WIDTH - 8, header_y + ROW_HEIGHT], fill="#f2f6f4", outline="#d9dcda")
    for index, column in enumerate(spec["columns"]):
        draw.text((COL_X[index] + 6, header_y + 8), column, fill="#1a1a1a", font=head_font)

    for row_index, row in enumerate(spec["rows"]):
        y = ROW_TOP + row_index * ROW_HEIGHT
        draw.rectangle([8, y, WIDTH - 8, y + ROW_HEIGHT], outline="#d9dcda")
        for col_index, cell in enumerate(row):
            anchor_x = COL_X[col_index] + 6
            draw.text((anchor_x, y + 8), cell, fill="#1a1a1a", font=body_font)

    buffer = BACKEND / ".seed-tmp.png"
    image.save(buffer)
    data = buffer.read_bytes()
    buffer.unlink()
    return data


def bbox(row_index: int, col_index: int) -> list[float]:
    """0~1 비율 좌표 [x, y, w, h]. 검증 화면 하이라이트에 사용한다."""
    x = COL_X[col_index] / WIDTH
    y = (ROW_TOP + row_index * ROW_HEIGHT) / HEIGHT
    return [x, y, COL_W[col_index] / WIDTH, ROW_HEIGHT / HEIGHT]


def payload_a() -> dict:
    return {
        "screen_type": "wip",
        "screen_title": CAPTURES[0]["title"],
        "as_of_date": "2025-12-31",
        "unit": "KRW",
        "filters": "Engagement = KOR01434",
        "rows": [
            {
                "row_index": 1,
                "wbs_code": {"value": "KOR01434-01-01-01-1000", "confidence": "high", "bbox": bbox(0, 0)},
                "period": {"from": "2025-05-01", "to": "2025-10-31"},
                "value_basis": "period",
                "fields": [
                    {"item_type": "time", "raw_label": "Time", "amount": 263_746_000,
                     "confidence": "high", "bbox": bbox(0, 2)},
                    {"item_type": "expense", "raw_label": "Expense", "amount": 6_216_247,
                     "confidence": "high", "bbox": bbox(0, 3)},
                ],
            },
            {
                "row_index": 2,
                "wbs_code": {"value": "KOR01434-01-01-01-1000", "confidence": "high", "bbox": bbox(1, 0)},
                "period": {"from": "2025-11-01", "to": "2025-12-31"},
                "value_basis": "period",
                "fields": [
                    {"item_type": "time", "raw_label": "Time", "amount": 8_030_000,
                     "confidence": "high", "bbox": bbox(1, 2)},
                    {"item_type": "expense", "raw_label": "Expense", "amount": 1_865_867,
                     "confidence": "high", "bbox": bbox(1, 3)},
                ],
            },
        ],
        "totals": [
            {"raw_label": "Total", "amount": 269_962_247, "row_index": 1},
            {"raw_label": "Total", "amount": 9_895_867, "row_index": 2},
        ],
        "arithmetic_checks": [{"rule": "time+expense=total", "passed": True, "diff": 0}],
    }


def payload_b() -> dict:
    return {
        "screen_type": "wip",
        "screen_title": CAPTURES[1]["title"],
        "as_of_date": "2025-12-31",
        "unit": "KRW",
        "rows": [
            {
                "row_index": 1,
                "wbs_code": {"value": "KOR01434-01-02-01-1000", "confidence": "high", "bbox": bbox(0, 0)},
                "period": {"from": "2025-11-01", "to": "2025-12-31"},
                "value_basis": "period",
                "fields": [
                    {"item_type": "time", "raw_label": "Time", "amount": 72_000_000,
                     "confidence": "high", "bbox": bbox(0, 2)},
                    {"item_type": "expense", "raw_label": "Expense", "amount": 5_629_160,
                     "confidence": "high", "bbox": bbox(0, 3)},
                ],
            },
            {
                "row_index": 2,
                "wbs_code": {"value": "KOR01434-01-02-01-1000", "confidence": "high", "bbox": bbox(1, 0)},
                "period": {"from": "2025-11-01", "to": "2025-12-31"},
                "value_basis": "period",
                "fields": [
                    {"item_type": "ltd", "raw_label": "LTD Adjustment", "amount": 10_000_000,
                     "confidence": "high", "bbox": bbox(1, 2)},
                    {"item_type": "contract_amount", "raw_label": "Change Order Amount",
                     "amount": 50_000_000, "confidence": "high", "bbox": bbox(1, 4)},
                ],
            },
        ],
        "totals": [{"raw_label": "Total", "amount": 77_629_160, "row_index": 1}],
    }


def payload_2() -> dict:
    return {
        "screen_type": "wip",
        "screen_title": CAPTURE_2["title"],
        "as_of_date": "2026-06-30",
        "unit": "KRW",
        "rows": [
            {
                "row_index": 1,
                "wbs_code": {"value": "KOR02201-01-01-01-1000", "confidence": "high", "bbox": bbox(0, 0)},
                "period": {"from": "2026-01-01", "to": "2026-06-30"},
                "value_basis": "period",
                "fields": [
                    {"item_type": "time", "raw_label": "Time", "amount": 512_400_000,
                     "confidence": "high", "bbox": bbox(0, 2)},
                    {"item_type": "expense", "raw_label": "Expense", "amount": 18_340_000,
                     "confidence": "high", "bbox": bbox(0, 3)},
                ],
            }
        ],
        "totals": [{"raw_label": "Total", "amount": 530_740_000, "row_index": 1}],
    }


def seed_second_project(session) -> None:
    """Backlog·Billing이 입력된 프로젝트를 확정 상태까지 만든다."""
    from datetime import date

    from app.models import BillingPlan, StaffingPlan
    from app.services import snapshots as snapshot_service
    from app.services import verification

    spec = EngagementCreate.model_validate(ENGAGEMENT_2)
    engagement = Engagement(
        name=spec.name,
        client=spec.client,
        engagement_code=spec.engagement_code,
        contract_type=spec.contract_type.value,
        ep=spec.ep,
        em=spec.em,
        start_date=spec.start_date,
        end_date=spec.end_date,
        currency=spec.currency,
    )
    session.add(engagement)
    session.flush()
    for contract in spec.contracts:
        _add_contract(session, engagement, ContractCreate.model_validate(contract.model_dump()))
    session.flush()

    upload, _ = upload_service.store_upload(
        session,
        engagement=engagement,
        filename=CAPTURE_2["filename"],
        content=render_capture(CAPTURE_2),
        uploaded_by="EM2",
    )
    session.flush()
    ingest_payload(session, upload, OcrPayload.model_validate(payload_2()))

    # 모든 값을 확인 처리하고 확정한다
    for record in upload.ocr_records:
        verification.apply_decision(
            session,
            record,
            verification.RecordDecision(ocr_record_id=record.id, action="confirm"),
            "EM2",
        )
    verification.confirm_upload(session, upload, actor="EM2")

    wbs = engagement.contracts[0].wbs_list[0]
    for row in STAFFING_2:
        session.add(
            StaffingPlan(
                wbs_id=wbs.id,
                person_or_grade=row["person_or_grade"],
                month=row["month"],
                remaining_mm=row["remaining_mm"],
                rate=row["rate"],
            )
        )
    session.add(
        BillingPlan(
            wbs_id=wbs.id,
            planned_amount=BILLING_2["planned_amount"],
            billed_amount=BILLING_2["billed_amount"],
            billing_date=date.fromisoformat(BILLING_2["billing_date"]),
        )
    )
    session.flush()
    snapshot_service.create_snapshot(session, engagement, label="초기 확정", actor="EM2")
    issues_service.refresh_action_items(session, engagement)
    session.flush()
    print(f"프로젝트 생성: {engagement.engagement_code} (Backlog·Billing 입력, 확정 완료)")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="기존 DB를 비우고 다시 생성")
    args = parser.parse_args()

    config.ensure_dirs()
    if args.reset:
        from app.db import engine

        Base.metadata.drop_all(bind=engine)
    init_db()

    with SessionLocal() as session:
        if session.query(Engagement).filter_by(engagement_code="KOR01434").first():
            print("KOR01434가 이미 있습니다. --reset 으로 다시 생성하십시오.")
            return

        spec = EngagementCreate.model_validate(ENGAGEMENT)
        engagement = Engagement(
            name=spec.name,
            client=spec.client,
            engagement_code=spec.engagement_code,
            contract_type=spec.contract_type.value,
            ep=spec.ep,
            em=spec.em,
            start_date=spec.start_date,
            end_date=spec.end_date,
            currency=spec.currency,
        )
        session.add(engagement)
        session.flush()
        for contract in spec.contracts:
            _add_contract(session, engagement, ContractCreate.model_validate(contract.model_dump()))
        session.flush()
        print(f"프로젝트 생성: {engagement.engagement_code}")

        for capture, payload in zip(CAPTURES, (payload_a(), payload_b()), strict=True):
            upload, duplicate = upload_service.store_upload(
                session,
                engagement=engagement,
                filename=capture["filename"],
                content=render_capture(capture),
                uploaded_by="EP",
            )
            session.flush()
            if duplicate:
                continue
            ingest_payload(session, upload, OcrPayload.model_validate(payload))
            created = issues_service.scan_upload(session, upload)
            print(
                f"캡처 판독: Upload #{upload.id} {capture['filename']} "
                f"행 {len(upload.ocr_records)}개, 이상징후 {len(created)}건"
            )

        if not session.query(Engagement).filter_by(engagement_code="KOR02201").first():
            seed_second_project(session)
        session.commit()

    print("\n데모 데이터 준비 완료. 검증 화면에서 값을 확인·확정하십시오.")


if __name__ == "__main__":
    main()
