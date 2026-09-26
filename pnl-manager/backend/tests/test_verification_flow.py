"""검증·확정 흐름(§FR-05), Snapshot(§FR-08), 오프라인 직접 입력(§9)."""

from __future__ import annotations

import pytest

from tests.fixtures_kor01434 import CAPTURE_A, ENGAGEMENT_PAYLOAD, WBS_1, WBS_2


@pytest.fixture()
def prepared(client, png_bytes):
    engagement = client.post("/api/engagements", json=ENGAGEMENT_PAYLOAD).json()
    upload = client.post(
        f"/api/engagements/{engagement['id']}/uploads",
        files=[("files", ("cap.png", png_bytes, "image/png"))],
    ).json()[0]["upload"]
    client.post(f"/api/uploads/{upload['id']}/ocr-payload", json={"payload": CAPTURE_A})
    wbs = client.get(f"/api/engagements/{engagement['id']}/wbs").json()
    return {
        "engagement": engagement,
        "upload": upload,
        "wbs_by_code": {w["code"]: w["id"] for w in wbs},
    }


def records(client, upload_id):
    return client.get(f"/api/uploads/{upload_id}/verification").json()["records"]


def test_rows_split_per_wbs_row_with_upload_relation_kept(client, prepared):
    """한 화면의 여러 행을 행 단위 레코드로 분리하되 Upload 관계를 유지한다(§FR-03)."""
    rows = records(client, prepared["upload"]["id"])
    assert {r["row_index"] for r in rows} == {1, 2}
    assert all(r["upload_id"] == prepared["upload"]["id"] for r in rows)
    assert {r["item_type"] for r in rows} == {"time", "expense"}
    assert all(r["wbs_code_raw"].startswith(WBS_1) for r in rows)
    # 화면 코드가 마스터보다 하위 레벨이어도 매칭된다
    assert all(r["wbs_id"] == prepared["wbs_by_code"][WBS_1] for r in rows)


def test_original_payload_preserved_immutably(client, prepared):
    """최초 판독값은 원본 그대로 보존한다(§6.1)."""
    upload_id = prepared["upload"]["id"]
    rows = records(client, upload_id)
    target = next(r for r in rows if r["item_type"] == "time" and r["row_index"] == 2)
    client.post(
        f"/api/uploads/{upload_id}/decisions",
        json={"decisions": [{"ocr_record_id": target["id"], "action": "edit",
                             "amount": 9_000_000}], "actor": "EP"},
    )
    after = next(
        r for r in records(client, upload_id) if r["id"] == target["id"]
    )
    assert after["amount"] == 8_030_000  # 판독값은 불변
    assert after["amount_raw"] == "8030000"

    view = client.get(f"/api/uploads/{upload_id}/verification").json()
    edited = next(c for c in view["confirmed"] if c["ocr_record_id"] == target["id"])
    assert edited["amount"] == 9_000_000
    assert edited["original_amount"] == 8_030_000  # 원본 판독값을 함께 표시
    assert edited["action"] == "edit"
    assert edited["confirmed_by"] == "EP"


def test_six_actions_supported(client, prepared):
    """값별 액션 6종(§FR-05)."""
    upload_id = prepared["upload"]["id"]
    rows = records(client, upload_id)
    target = rows[0]

    for action, extra in [
        ("confirm", {}),
        ("edit", {"amount": 1_000}),
        ("exclude", {}),
        ("duplicate", {}),
        ("reassign", {"wbs_id": prepared["wbs_by_code"][WBS_2]}),
    ]:
        response = client.post(
            f"/api/uploads/{upload_id}/decisions",
            json={"decisions": [{"ocr_record_id": target["id"], "action": action, **extra}]},
        )
        assert response.status_code == 200, response.text
        confirmed = next(
            c for c in response.json()["confirmed"] if c["ocr_record_id"] == target["id"]
        )
        assert confirmed["action"] == action

    # 판독 실패 표시는 직접 입력을 요구하므로 확정되지 않는다
    failed = client.post(
        f"/api/uploads/{upload_id}/decisions",
        json={"decisions": [{"ocr_record_id": target["id"], "action": "failed"}]},
    )
    assert failed.status_code == 422
    assert "직접 입력" in failed.json()["detail"]


def test_reassign_requires_target_wbs(client, prepared):
    upload_id = prepared["upload"]["id"]
    target = records(client, upload_id)[0]
    response = client.post(
        f"/api/uploads/{upload_id}/decisions",
        json={"decisions": [{"ocr_record_id": target["id"], "action": "reassign"}]},
    )
    assert response.status_code == 422
    assert "재분류 대상 WBS" in response.json()["detail"]


def test_excluded_record_is_not_calculated(client, prepared):
    """제외·중복 처리된 값은 손익 계산에서 배제된다(§FR-10)."""
    upload_id = prepared["upload"]["id"]
    eid = prepared["engagement"]["id"]
    rows = records(client, upload_id)
    decisions = []
    for row in rows:
        action = "exclude" if row["row_index"] == 2 else "confirm"
        decisions.append({"ocr_record_id": row["id"], "action": action})
    client.post(f"/api/uploads/{upload_id}/decisions", json={"decisions": decisions})
    result = client.post(f"/api/uploads/{upload_id}/confirm", json={"actor": "EP"})
    assert result.status_code == 200, result.text

    pnl = client.get(f"/api/engagements/{eid}/pnl").json()
    assert pnl["cumulative_usage"] == 269_962_247  # 2행 9,895,867원 제외


def test_partial_confirmation_allowed(client, prepared):
    """부분 확정(일부 행 제외)을 허용한다(§FR-05)."""
    upload_id = prepared["upload"]["id"]
    rows = records(client, upload_id)
    decisions = [
        {"ocr_record_id": r["id"], "action": "confirm" if r["row_index"] == 1 else "duplicate"}
        for r in rows
    ]
    view = client.post(
        f"/api/uploads/{upload_id}/decisions", json={"decisions": decisions}
    ).json()
    assert view["gate"]["can_confirm"] is True
    assert client.post(f"/api/uploads/{upload_id}/confirm", json={}).status_code == 200


def test_manual_record_for_offline_entry(client, prepared):
    """오프라인·판독 실패 시 직접 입력으로 계산이 가능하다(§9 가용성)."""
    upload_id = prepared["upload"]["id"]
    eid = prepared["engagement"]["id"]
    rows = records(client, upload_id)
    client.post(
        f"/api/uploads/{upload_id}/decisions",
        json={"decisions": [{"ocr_record_id": r["id"], "action": "confirm"} for r in rows]},
    )
    response = client.post(
        f"/api/uploads/{upload_id}/manual-records",
        json={
            "item_type": "os",
            "wbs_id": prepared["wbs_by_code"][WBS_1],
            "amount": 5_000_000,
            "period_from": "2025-05-01",
            "period_to": "2025-10-31",
            "raw_label": "Outside Service(직접 입력)",
            "actor": "EM",
        },
    )
    assert response.status_code == 200, response.text
    view = response.json()
    assert view["gate"]["can_confirm"] is True

    client.post(f"/api/uploads/{upload_id}/confirm", json={"actor": "EM"})
    pnl = client.get(f"/api/engagements/{eid}/pnl").json()
    assert pnl["cumulative_usage"] == 269_962_247 + 9_895_867 + 5_000_000


def test_snapshot_history_is_append_only(client, prepared):
    """Snapshot은 덮어쓰지 않고 누적된다(§FR-08)."""
    upload_id = prepared["upload"]["id"]
    eid = prepared["engagement"]["id"]
    rows = records(client, upload_id)
    client.post(
        f"/api/uploads/{upload_id}/decisions",
        json={"decisions": [{"ocr_record_id": r["id"], "action": "confirm"} for r in rows]},
    )
    first = client.post(f"/api/uploads/{upload_id}/confirm", json={}).json()["snapshot_id"]
    second = client.post(
        f"/api/engagements/{eid}/snapshots", params={"label": "수동 Snapshot"}
    ).json()["id"]
    assert first != second

    snapshots = client.get(f"/api/engagements/{eid}/snapshots").json()
    assert [s["id"] for s in snapshots] == [second, first]

    detail = client.get(f"/api/snapshots/{first}").json()
    assert detail["values"]
    assert detail["result"]["formula_version"] == "1.0.0"

    diff = client.get(f"/api/snapshots/{second}/diff").json()
    assert diff["previous_snapshot_id"] == first
    assert diff["items"]["time"]["delta"] == 0


def test_snapshot_diff_tracks_increase(client, prepared):
    """연속 Snapshot 간 Time·Expense 증가액을 추적한다(§FR-08)."""
    upload_id = prepared["upload"]["id"]
    eid = prepared["engagement"]["id"]
    rows = records(client, upload_id)
    row1 = [r for r in rows if r["row_index"] == 1]
    client.post(
        f"/api/uploads/{upload_id}/decisions",
        json={
            "decisions": [{"ocr_record_id": r["id"], "action": "confirm"} for r in row1]
            + [
                {"ocr_record_id": r["id"], "action": "exclude"}
                for r in rows
                if r["row_index"] == 2
            ]
        },
    )
    first = client.post(f"/api/uploads/{upload_id}/confirm", json={}).json()["snapshot_id"]

    # 2행을 다시 확인 처리하면 발생액이 늘어난다
    client.post(
        f"/api/uploads/{upload_id}/decisions",
        json={
            "decisions": [
                {"ocr_record_id": r["id"], "action": "confirm"}
                for r in rows
                if r["row_index"] == 2
            ]
        },
    )
    second = client.post(
        f"/api/engagements/{eid}/snapshots", params={"label": "2행 반영"}
    ).json()["id"]

    diff = client.get(f"/api/snapshots/{second}/diff").json()
    assert diff["previous_snapshot_id"] == first
    assert diff["items"]["time"]["delta"] == 8_030_000
    assert diff["items"]["expense"]["delta"] == 1_865_867


def test_audit_log_records_every_change(client, prepared, session):
    """모든 확정·수정에 수정자·시점·전후 값이 기록된다(§9 감사 추적)."""
    from app.models import AuditLog

    upload_id = prepared["upload"]["id"]
    target = records(client, upload_id)[0]
    client.post(
        f"/api/uploads/{upload_id}/decisions",
        json={"decisions": [{"ocr_record_id": target["id"], "action": "edit",
                             "amount": 123}], "actor": "EP"},
    )
    logs = session.query(AuditLog).filter(AuditLog.entity == "confirmed_record").all()
    assert logs
    entry = logs[-1]
    assert entry.actor == "EP"
    assert entry.at is not None
    assert "123" in entry.after


def test_unsupported_file_type_rejected(client, prepared):
    response = client.post(
        f"/api/engagements/{prepared['engagement']['id']}/uploads",
        files=[("files", ("data.pdf", b"%PDF-1.4", "application/pdf"))],
    )
    assert response.status_code == 400
    assert "지원하지 않는 형식" in response.json()["detail"]


def test_contract_period_overlap_rejected(client, prepared):
    """계약 차수 유효기간 겹침 검사(§7)."""
    response = client.post(
        f"/api/engagements/{prepared['engagement']['id']}/contracts",
        json={"seq": 2, "amount": 1_000, "valid_from": "2025-10-01", "valid_to": "2025-11-30"},
    )
    assert response.status_code == 409
    assert "겹칩니다" in response.json()["detail"]


def test_duplicate_engagement_code_rejected(client, prepared):
    response = client.post("/api/engagements", json=ENGAGEMENT_PAYLOAD)
    assert response.status_code == 409


def test_billing_plan_with_zero_planned_amount_is_respected(client, prepared, session):
    """Billing 계획이 0원으로 등록되면 실적 청구액으로 대체하지 않는다."""
    from app.models import BillingPlan

    eid = prepared["engagement"]["id"]
    upload_id = prepared["upload"]["id"]
    rows = records(client, upload_id)
    client.post(
        f"/api/uploads/{upload_id}/decisions",
        json={"decisions": [{"ocr_record_id": r["id"], "action": "confirm"} for r in rows]},
    )
    client.post(f"/api/uploads/{upload_id}/confirm", json={})

    session.add(BillingPlan(wbs_id=prepared["wbs_by_code"][WBS_1], planned_amount=0, billed_amount=0))
    session.flush()

    pnl = client.get(f"/api/engagements/{eid}/pnl").json()
    # 계획 청구액 0원이 그대로 반영되어 종료예상 WIP는 종료예상 사용액과 같다
    assert pnl["expected_end_wip"] == pnl["eac"]
