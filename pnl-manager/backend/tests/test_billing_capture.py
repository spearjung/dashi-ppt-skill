"""Billing 화면 캡처 → 확정 → 손익 반영(§FR-02·03·10).

Billing 금액은 화면 캡처로 입력되므로, 청구 예정액·완료액·미청구액·
청구가능 경비가 판독에서 계산까지 그대로 이어지는지 확인한다.
"""

from __future__ import annotations

import pytest

from tests.fixtures_kor01434 import CAPTURE_A, ENGAGEMENT_PAYLOAD, WBS_1

BILLING_CAPTURE = {
    "screen_type": "billing",
    "screen_title": "Billing Summary (단위: 원)",
    "as_of_date": "2025-12-31",
    "unit": "KRW",
    "rows": [
        {
            "row_index": 1,
            "wbs_code": {"value": f"{WBS_1}-01-1000", "confidence": "high"},
            "period": {"from": "2025-05-01", "to": "2025-12-31"},
            "value_basis": "cumulative",
            "fields": [
                {
                    "item_type": "billing_planned",
                    "raw_label": "Planned Billing",
                    "amount": 238_000_000,
                    "confidence": "high",
                },
                {
                    "item_type": "billing",
                    "raw_label": "Billed Amount",
                    "amount": 190_000_000,
                    "confidence": "high",
                },
                {
                    "item_type": "billing_unbilled",
                    "raw_label": "Unbilled",
                    "amount": 48_000_000,
                    "confidence": "high",
                },
                {
                    "item_type": "billable_expense",
                    "raw_label": "Billable Expense",
                    "amount": 6_216_247,
                    "confidence": "high",
                },
            ],
        }
    ],
}


def _confirm(client, upload_id: int) -> None:
    view = client.get(f"/api/uploads/{upload_id}/verification").json()
    client.post(
        f"/api/uploads/{upload_id}/decisions",
        json={
            "decisions": [{"ocr_record_id": r["id"], "action": "confirm"} for r in view["records"]],
            "actor": "EP",
        },
    )
    result = client.post(f"/api/uploads/{upload_id}/confirm", json={"actor": "EP"})
    assert result.status_code == 200, result.text


@pytest.fixture()
def billing_confirmed(client, png_bytes, png_bytes_alt):
    engagement = client.post("/api/engagements", json=ENGAGEMENT_PAYLOAD).json()
    eid = engagement["id"]
    for content, name, payload in (
        (png_bytes, "wip.png", CAPTURE_A),
        (png_bytes_alt, "billing.png", BILLING_CAPTURE),
    ):
        upload = client.post(
            f"/api/engagements/{eid}/uploads",
            files=[("files", (name, content, "image/png"))],
        ).json()[0]["upload"]
        response = client.post(f"/api/uploads/{upload['id']}/ocr-payload", json={"payload": payload})
        assert response.status_code == 200, response.text
        _confirm(client, upload["id"])
    return eid


def test_billing_screen_is_classified_and_fields_are_high_impact(client, png_bytes):
    engagement = client.post("/api/engagements", json=ENGAGEMENT_PAYLOAD).json()
    upload = client.post(
        f"/api/engagements/{engagement['id']}/uploads",
        files=[("files", ("billing.png", png_bytes, "image/png"))],
    ).json()[0]["upload"]
    client.post(f"/api/uploads/{upload['id']}/ocr-payload", json={"payload": BILLING_CAPTURE})

    detail = client.get(f"/api/uploads/{upload['id']}").json()
    assert detail["screen_type"] == "billing"
    assert detail["unit"] == "KRW"

    view = client.get(f"/api/uploads/{upload['id']}/verification").json()
    by_item = {r["item_type"]: r for r in view["records"]}
    assert set(by_item) == {"billing_planned", "billing", "billing_unbilled", "billable_expense"}
    # 청구 예정액·완료액·미청구액은 고영향 → 개별 확인 필요
    for item in ("billing_planned", "billing", "billing_unbilled"):
        assert by_item[item]["high_impact"] is True
        assert by_item[item]["needs_individual_confirmation"] is True
    # 누적값 기준으로 저장된다
    assert by_item["billing"]["value_basis"] == "cumulative"
    assert view["gate"]["can_confirm"] is False


def test_billing_capture_flows_into_pnl(client, billing_confirmed):
    """캡처된 청구 금액이 손익 계산에 그대로 반영된다."""
    pnl = client.get(f"/api/engagements/{billing_confirmed}/pnl").json()

    assert pnl["total_billing"] == 190_000_000
    assert pnl["total_planned_billing"] == 238_000_000
    # 미청구액은 화면 표시값을 우선한다(누적 사용액 − 청구액으로 재계산하지 않음)
    assert pnl["unbilled_amount"] == 48_000_000
    assert pnl["total_billable_expense"] == 6_216_247

    # 현재 WIP = Time + Expense − Billing (1차 WBS 누적 279,858,114 − 190,000,000)
    wbs = next(w for w in pnl["wbs_results"] if w["code"] == WBS_1)
    assert wbs["billing"] == 190_000_000
    assert wbs["current_wip"] == 279_858_114 - 190_000_000
    # 종료예상 WIP = 종료예상 사용액 − 총 Billing 예정액
    assert pnl["expected_end_wip"] == pnl["eac"] - 238_000_000


def test_billing_plan_is_replaced_on_recapture(client, billing_confirmed, png_bytes_alt):
    """같은 Billing 화면을 다시 판독·확정하면 계획이 중복 생성되지 않는다."""
    before = client.get(f"/api/engagements/{billing_confirmed}/pnl").json()

    uploads = client.get(f"/api/engagements/{billing_confirmed}/uploads").json()
    billing_upload = next(u for u in uploads if u["screen_type"] == "billing")

    updated = dict(BILLING_CAPTURE)
    updated["rows"] = [dict(BILLING_CAPTURE["rows"][0])]
    updated["rows"][0]["fields"] = [
        {**field, "amount": field["amount"] + 10_000_000}
        if field["item_type"] == "billing"
        else field
        for field in BILLING_CAPTURE["rows"][0]["fields"]
    ]
    client.post(f"/api/uploads/{billing_upload['id']}/ocr-payload", json={"payload": updated})
    _confirm(client, billing_upload["id"])

    after = client.get(f"/api/engagements/{billing_confirmed}/pnl").json()
    assert before["total_billing"] == 190_000_000
    assert after["total_billing"] == 200_000_000  # 누적 합산이 아니라 대체
    assert after["total_planned_billing"] == 238_000_000


def test_unbilled_action_item_closes_when_capture_clears_condition(client, billing_confirmed):
    """캡처된 미청구액이 기준치 아래면 미청구 조치사항이 자동으로 닫힌다.

    Billing 화면이 없을 때는 누적 사용액 전액을 미청구로 보아 조치사항이 열리지만,
    캡처로 실제 미청구액(48,000,000원 < 기준치 50,000,000원)이 확정되면 해소된다.
    """
    issues = client.get(f"/api/engagements/{billing_confirmed}/issues").json()
    billing_action = next(i for i in issues if i["type"] == "billing_action")
    assert billing_action["status"] == "resolved"
    assert billing_action["selected_action"] == "condition_cleared"
    assert "조건이 해소되어" in billing_action["detail"]

    # 대시보드의 미해결 카운트에서도 빠진다
    dashboard = client.get("/api/dashboard").json()
    project = next(p for p in dashboard["projects"] if p["engagement_id"] == billing_confirmed)
    assert all("미청구" not in reason for reason in
               next(a["reasons"] for a in dashboard["action_required"]
                    if a["engagement_id"] == billing_confirmed))
    assert project["unbilled_amount"] == 48_000_000


def test_unbilled_action_item_uses_captured_amount_when_over_threshold(client, png_bytes, png_bytes_alt):
    """미청구액이 기준치를 넘으면 캡처된 금액으로 조치사항이 등록된다."""
    engagement = client.post("/api/engagements", json=ENGAGEMENT_PAYLOAD).json()
    eid = engagement["id"]
    over_threshold = {
        **BILLING_CAPTURE,
        "rows": [
            {
                **BILLING_CAPTURE["rows"][0],
                "fields": [
                    {**field, "amount": 120_000_000}
                    if field["item_type"] == "billing_unbilled"
                    else field
                    for field in BILLING_CAPTURE["rows"][0]["fields"]
                ],
            }
        ],
    }
    for content, name, payload in (
        (png_bytes, "wip.png", CAPTURE_A),
        (png_bytes_alt, "billing.png", over_threshold),
    ):
        upload = client.post(
            f"/api/engagements/{eid}/uploads",
            files=[("files", (name, content, "image/png"))],
        ).json()[0]["upload"]
        client.post(f"/api/uploads/{upload['id']}/ocr-payload", json={"payload": payload})
        _confirm(client, upload["id"])

    issues = client.get(f"/api/engagements/{eid}/issues").json()
    billing_action = next(
        i for i in issues if i["type"] == "billing_action" and i["status"] == "open"
    )
    assert "120,000,000" in billing_action["title"]
    # 상세에 청구 예정·완료액을 함께 보여준다
    assert "238,000,000" in billing_action["detail"]
    assert "190,000,000" in billing_action["detail"]
