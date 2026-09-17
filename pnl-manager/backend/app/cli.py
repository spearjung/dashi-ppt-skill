"""Phase 0 초기 검증용 CLI(§11).

흐름: 캡처 업로드 → 표·숫자 추출 → 데이터 행 CSV 변환 → 사용자 오류 수정(CSV 편집)
      → 프로젝트·WBS별 누적 → 손익·LTD 계산 → HTML 리포트 출력

사용 예
  python -m app.cli init
  python -m app.cli create-project docs/sample-project.json
  python -m app.cli ingest KOR01434 capture1.png capture2.png --payload capture1.ocr.json
  python -m app.cli export-csv KOR01434 rows.csv
  python -m app.cli import-csv KOR01434 rows.csv --actor EP
  python -m app.cli report KOR01434 report.html
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from sqlalchemy import select

from . import config
from .db import SessionLocal, init_db
from .enums import RecordAction, UploadStatus
from .models import Engagement, Upload
from .ocr.pipeline import ingest_payload, run_ocr
from .ocr.schema import OcrPayload
from .ocr.units import format_krw
from .services import issues as issues_service
from .services import pnl as pnl_service
from .services import snapshots as snapshot_service
from .services import uploads as upload_service
from .services import verification

CSV_COLUMNS = [
    "ocr_record_id",
    "upload_id",
    "row_index",
    "wbs_code_raw",
    "wbs_code",
    "item_type",
    "raw_label",
    "amount_raw",
    "amount",
    "unit",
    "value_basis",
    "period_from",
    "period_to",
    "confidence",
    "confidence_reason",
    "duplicate_verdict",
    "high_impact",
    "action",
]


def _engagement(session, code: str) -> Engagement:
    engagement = session.execute(
        select(Engagement).where(Engagement.engagement_code == code)
    ).scalars().first()
    if engagement is None:
        raise SystemExit(f"Engagement Code {code}를 찾을 수 없습니다.")
    return engagement


def cmd_init(_args) -> None:
    init_db()
    print(f"DB 초기화 완료: {config.DB_PATH}")
    print(f"업로드 경로: {config.UPLOAD_DIR}")


def cmd_create_project(args) -> None:
    """프로젝트 마스터를 JSON으로 생성한다(§FR-01)."""
    from .api.engagements import _add_contract
    from .schemas import ContractCreate, EngagementCreate

    payload = EngagementCreate.model_validate(json.loads(Path(args.file).read_text(encoding="utf-8")))
    init_db()
    with SessionLocal() as session:
        engagement = Engagement(
            name=payload.name,
            client=payload.client,
            engagement_code=payload.engagement_code,
            contract_type=payload.contract_type.value,
            ep=payload.ep,
            em=payload.em,
            start_date=payload.start_date,
            end_date=payload.end_date,
            currency=payload.currency,
        )
        session.add(engagement)
        session.flush()
        for contract in sorted(payload.contracts, key=lambda c: c.seq):
            _add_contract(session, engagement, ContractCreate.model_validate(contract.model_dump()))
        session.commit()
        print(f"생성 완료: {engagement.engagement_code} (#{engagement.id})")
        for contract in engagement.contracts:
            print(
                f"  차수 {contract.seq}: {format_krw(contract.amount)} "
                f"({contract.valid_from} ~ {contract.valid_to}) "
                f"WBS {[w.code for w in contract.wbs_list]}"
            )


def cmd_ingest(args) -> None:
    """캡처를 업로드하고 판독한다. --payload 로 판독 결과 JSON을 직접 줄 수 있다."""
    init_db()
    with SessionLocal() as session:
        engagement = _engagement(session, args.code)
        payloads = [Path(p) for p in (args.payload or [])]
        for index, image in enumerate(args.images):
            path = Path(image)
            upload, duplicate = upload_service.store_upload(
                session,
                engagement=engagement,
                filename=path.name,
                content=path.read_bytes(),
                screen_type=args.screen_type,
                uploaded_by=args.actor,
            )
            session.flush()
            if duplicate:
                print(f"[중복] {path.name} → 기존 Upload #{upload.id}에 연결, 자동 확정 안 함")
                continue

            if index < len(payloads):
                payload = OcrPayload.model_validate(
                    json.loads(payloads[index].read_text(encoding="utf-8"))
                )
                ingest_payload(session, upload, payload)
            else:
                run_ocr(session, upload)
            created = issues_service.scan_upload(session, upload)
            session.commit()
            print(
                f"[판독] Upload #{upload.id} {path.name} "
                f"유형={upload.screen_type}({upload.screen_type_source}) "
                f"행={len(upload.ocr_records)}개 이상징후={len(created)}건"
            )
            for warning in upload.warnings or []:
                print(f"       경고: {warning}")


def cmd_export_csv(args) -> None:
    """판독 결과를 CSV로 내보낸다. action 열을 편집해 오류를 수정한다."""
    with SessionLocal() as session:
        engagement = _engagement(session, args.code)
        uploads = list(
            session.execute(
                select(Upload).where(
                    Upload.engagement_id == engagement.id,
                    Upload.status != UploadStatus.CONFIRMED.value,
                )
            ).scalars()
        )
        rows = []
        for upload in uploads:
            for record in upload.ocr_records:
                rows.append(
                    {
                        "ocr_record_id": record.id,
                        "upload_id": upload.id,
                        "row_index": record.row_index,
                        "wbs_code_raw": record.wbs_code_raw or "",
                        "wbs_code": record.wbs.code if record.wbs else "",
                        "item_type": record.item_type,
                        "raw_label": record.raw_label or "",
                        "amount_raw": record.amount_raw or "",
                        "amount": "" if record.amount is None else record.amount,
                        "unit": record.unit or "",
                        "value_basis": record.value_basis,
                        "period_from": record.period_from or "",
                        "period_to": record.period_to or "",
                        "confidence": record.confidence,
                        "confidence_reason": record.confidence_reason or "",
                        "duplicate_verdict": record.duplicate_verdict,
                        "high_impact": "Y" if record.high_impact else "",
                        "action": "confirm",
                    }
                )
        target = Path(args.out)
        with target.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
            writer.writeheader()
            writer.writerows(rows)
        print(f"{len(rows)}행을 {target}에 저장했습니다.")
        print("action 열을 confirm/edit/exclude/reassign/duplicate 중 하나로 편집하십시오.")
        print("edit 시 amount 열을 원 단위 정수로, reassign 시 wbs_code 열을 수정하십시오.")


def cmd_import_csv(args) -> None:
    """편집된 CSV를 반영해 확정하고 Snapshot을 만든다."""
    from .models import Contract, OcrRecord, Wbs

    with SessionLocal() as session:
        engagement = _engagement(session, args.code)
        wbs_by_code = {
            w.code: w.id
            for w in session.execute(
                select(Wbs).join(Contract, Wbs.contract_id == Contract.id).where(
                    Contract.engagement_id == engagement.id
                )
            ).scalars()
        }
        touched: set[int] = set()
        with Path(args.file).open(newline="", encoding="utf-8-sig") as handle:
            for line in csv.DictReader(handle):
                record = session.get(OcrRecord, int(line["ocr_record_id"]))
                if record is None:
                    continue
                action = (line.get("action") or "confirm").strip() or "confirm"
                amount = (line.get("amount") or "").strip()
                wbs_code = (line.get("wbs_code") or "").strip()
                decision = verification.RecordDecision(
                    ocr_record_id=record.id,
                    action=action,
                    amount=int(float(amount)) if amount and action == RecordAction.EDIT.value else None,
                    unit=None,
                    wbs_id=wbs_by_code.get(wbs_code) if wbs_code else None,
                    value_basis=(line.get("value_basis") or "").strip() or None,
                    note="CLI CSV 반영",
                )
                verification.apply_decision(session, record, decision, args.actor)
                touched.add(record.upload_id)

        for upload_id in sorted(touched):
            upload = session.get(Upload, upload_id)
            gate = verification.confirmation_gate(upload)
            if not gate.can_confirm:
                print(f"[보류] Upload #{upload_id}: {' / '.join(gate.blockers)}")
                continue
            verification.confirm_upload(session, upload, actor=args.actor)
            print(f"[확정] Upload #{upload_id}")

        snapshot = snapshot_service.create_snapshot(
            session, engagement, label="CLI 확정", actor=args.actor
        )
        issues_service.refresh_action_items(session, engagement)
        session.commit()
        print(f"Snapshot #{snapshot.id} 생성 (기준일 {snapshot.as_of_date})")


def cmd_report(args) -> None:
    """손익·LTD 계산 결과를 HTML 리포트로 출력한다."""
    with SessionLocal() as session:
        engagement = _engagement(session, args.code)
        pnl = pnl_service.compute(session, engagement)
        scenarios = pnl_service.scenarios(session, engagement)
        open_issues = issues_service.open_issues(session, engagement.id)
        snapshot = snapshot_service.latest_snapshot(session, engagement.id)
        html = _render_html(engagement, pnl, scenarios, open_issues, snapshot)
        Path(args.out).write_text(html, encoding="utf-8")
        print(f"리포트 저장: {args.out}")
        print(f"  총 계약금액   {format_krw(pnl.total_contract_amount)}")
        print(f"  누적 사용액   {format_krw(pnl.cumulative_usage)}")
        print(f"  종료예상액    {format_krw(pnl.eac)}{' (잠정)' if pnl.provisional else ''}")
        print(f"  최종 예상잔액 {format_krw(pnl.final_expected_balance)}")
        print(f"  LTD 필요액    {format_krw(pnl.ltd_required)}")


def _render_html(engagement, pnl, scenarios, open_issues, snapshot) -> str:
    def krw(value):
        return "-" if value is None else f"{value:,}"

    wbs_rows = "".join(
        f"<tr><td>{w.code}</td><td class='n'>{w.contract_seq}차</td>"
        f"<td class='n'>{krw(w.allocated_contract_amount)}</td>"
        f"<td class='n'>{krw(w.cumulative_usage)}</td>"
        f"<td class='n'>{krw(w.remaining_input_estimate)}"
        f"{'' if w.backlog_entered else ' <span class=warn>미입력</span>'}</td>"
        f"<td class='n'>{krw(w.eac)}</td>"
        f"<td class='n {'neg' if w.final_expected_balance < 0 else ''}'>"
        f"{krw(w.final_expected_balance)}</td>"
        f"<td class='n'>{krw(w.ltd_required)}</td>"
        f"<td class='n'>{krw(w.ltd_outstanding)}</td></tr>"
        for w in pnl.wbs_results
    )
    def pct(value):
        return "-" if value is None else f"{value * 100:.1f}%"

    def mm(value):
        return "-" if value is None else f"{value:,.2f}"

    scenario_rows = "".join(
        f"<tr><td>{s['kind']}</td><td class='n'>{krw(s['eac'])}</td>"
        f"<td class='n'>{krw(s['expected_end_wip'])}</td>"
        f"<td class='n'>{krw(s['ltd_required'])}</td>"
        f"<td class='n'>{krw(s['additional_contract_needed'])}</td>"
        f"<td class='n'>{mm(s['required_mm_reduction'])}</td>"
        f"<td class='n'>{pct(s['expected_margin_rate'])}</td></tr>"
        for s in scenarios
    )
    issue_rows = "".join(
        f"<tr><td>{i.type}</td><td>{i.severity}</td><td>{i.title}</td><td>{i.detail or ''}</td></tr>"
        for i in open_issues
    ) or "<tr><td colspan=4>미해결 이상징후 없음</td></tr>"
    warnings = "".join(f"<li>{w}</li>" for w in pnl.warnings) or "<li>없음</li>"

    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<title>{engagement.name} 손익 리포트</title>
<style>
 body {{ font-family: -apple-system, 'Malgun Gothic', sans-serif; margin: 32px; color: #1a1a1a; }}
 h1 {{ font-size: 20px; border-bottom: 2px solid #006940; padding-bottom: 8px; }}
 h2 {{ font-size: 15px; margin-top: 28px; color: #006940; }}
 table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
 th, td {{ border: 1px solid #d7d7d7; padding: 6px 8px; text-align: left; }}
 th {{ background: #f2f6f4; }}
 td.n {{ text-align: right; font-variant-numeric: tabular-nums; }}
 .neg {{ color: #c0392b; font-weight: 600; }}
 .warn {{ color: #b8860b; font-size: 11px; }}
 .kpi {{ display: flex; gap: 12px; flex-wrap: wrap; margin: 12px 0 0; padding: 0; list-style: none; }}
 .kpi li {{ border: 1px solid #d7d7d7; border-radius: 6px; padding: 10px 14px; min-width: 150px; }}
 .kpi b {{ display: block; font-size: 16px; font-variant-numeric: tabular-nums; }}
 .kpi span {{ font-size: 11px; color: #666; }}
 ul.note {{ font-size: 12px; color: #555; }}
</style></head><body>
<h1>{engagement.name} ({engagement.engagement_code}) 손익 리포트</h1>
<p>고객사 {engagement.client} · 계약유형 {engagement.contract_type} · EP {engagement.ep or '-'}
   · 계약기간 {engagement.start_date} ~ {engagement.end_date}<br>
   최신 Snapshot #{snapshot.id if snapshot else '-'}
   (기준일 {snapshot.as_of_date if snapshot and snapshot.as_of_date else '-'})
   · 산식 버전 {pnl.formula_version}</p>
<ul class="kpi">
 <li><span>총 계약금액</span><b>{krw(pnl.total_contract_amount)}</b></li>
 <li><span>누적 사용액</span><b>{krw(pnl.cumulative_usage)}</b></li>
 <li><span>잔여 투입 예상액</span><b>{krw(pnl.remaining_input_estimate)}{'' if pnl.backlog_entered else ' (미입력)'}</b></li>
 <li><span>종료예상 사용액</span><b>{krw(pnl.eac)}{' 잠정' if pnl.provisional else ''}</b></li>
 <li><span>최종 예상 잔액</span><b class="{'neg' if pnl.final_expected_balance < 0 else ''}">{krw(pnl.final_expected_balance)}</b></li>
 <li><span>LTD 필요액</span><b>{krw(pnl.ltd_required)}</b></li>
 <li><span>종료예상 WIP</span><b>{krw(pnl.expected_end_wip)}</b></li>
 <li><span>예상 손익률</span><b>{'-' if pnl.expected_margin_rate is None else f'{pnl.expected_margin_rate * 100:.1f}%'}</b></li>
</ul>
<h2>WBS별 손익</h2>
<table><thead><tr><th>WBS</th><th>차수</th><th>계약금액(배분)</th><th>누적 사용액</th>
 <th>잔여 투입</th><th>종료예상액</th><th>최종 예상잔액</th><th>LTD 필요액</th><th>LTD 잔여</th></tr></thead>
<tbody>{wbs_rows}</tbody></table>
<h2>시나리오</h2>
<table><thead><tr><th>구분</th><th>종료예상액</th><th>종료예상 WIP</th><th>LTD 필요액</th>
 <th>추가계약 필요액</th><th>절감 필요 MM</th><th>예상 손익률</th></tr></thead>
<tbody>{scenario_rows}</tbody></table>
<h2>미해결 이상징후·조치사항</h2>
<table><thead><tr><th>유형</th><th>심각도</th><th>제목</th><th>내용</th></tr></thead>
<tbody>{issue_rows}</tbody></table>
<h2>검증 경고</h2>
<ul class="note">{warnings}</ul>
<p class="warn">단위: 원(KRW). 확정값만 계산에 반영됨. OCR 판독값은 임시값으로 제외됨.</p>
</body></html>"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pnl", description="프로젝트 손익관리 CLI(Phase 0)")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="DB·디렉터리 초기화").set_defaults(func=cmd_init)

    create = sub.add_parser("create-project", help="프로젝트 마스터 생성(JSON)")
    create.add_argument("file")
    create.set_defaults(func=cmd_create_project)

    ingest = sub.add_parser("ingest", help="캡처 업로드·판독")
    ingest.add_argument("code")
    ingest.add_argument("images", nargs="+")
    ingest.add_argument("--payload", nargs="*", help="판독 결과 JSON(이미지 순서대로)")
    ingest.add_argument("--screen-type", default=None)
    ingest.add_argument("--actor", default=None)
    ingest.set_defaults(func=cmd_ingest)

    export = sub.add_parser("export-csv", help="판독 결과 CSV 내보내기")
    export.add_argument("code")
    export.add_argument("out")
    export.set_defaults(func=cmd_export_csv)

    importer = sub.add_parser("import-csv", help="편집된 CSV 반영·확정")
    importer.add_argument("code")
    importer.add_argument("file")
    importer.add_argument("--actor", default=None)
    importer.set_defaults(func=cmd_import_csv)

    report = sub.add_parser("report", help="HTML 손익 리포트 출력")
    report.add_argument("code")
    report.add_argument("out")
    report.set_defaults(func=cmd_report)

    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
