"""조치사항 선택·해소(§FR-09, §FR-12)."""

from __future__ import annotations

import pytest

from app.rules.anomalies import ACTION_LABELS, WBS_ATTRIBUTION_ACTIONS
from tests.fixtures_kor01434 import CAPTURE_A, CAPTURE_B, ENGAGEMENT_PAYLOAD, WBS_2


@pytest.fixture()
def confirmed(client, png_bytes, png_bytes_alt):
    engagement = client.post("/api/engagements", json=ENGAGEMENT_PAYLOAD).json()
    eid = engagement["id"]
    for content, name, payload in (
        (png_bytes, "a.png", CAPTURE_A),
        (png_bytes_alt, "b.png", CAPTURE_B),
    ):
        upload = client.post(
            f"/api/engagements/{eid}/uploads",
            files=[("files", (name, content, "image/png"))],
        ).json()[0]["upload"]
        client.post(f"/api/uploads/{upload['id']}/ocr-payload", json={"payload": payload})
        view = client.get(f"/api/uploads/{upload['id']}/verification").json()
        client.post(
            f"/api/uploads/{upload['id']}/decisions",
            json={
                "decisions": [{"ocr_record_id": r["id"], "action": "confirm"} for r in view["records"]],
                "actor": "EP",
            },
        )
        client.post(f"/api/uploads/{upload['id']}/confirm", json={"actor": "EP"})
    return eid


def test_every_suggested_action_has_korean_label(confirmed, client):
    """제안 조치는 모두 한국어 라벨을 갖는다(원시 키 노출 금지)."""
    issues = client.get(f"/api/engagements/{confirmed}/issues").json()
    assert issues
    for issue in issues:
        assert issue["suggested_actions"], issue
        for action in issue["suggested_actions"]:
            assert action["label"] != action["key"], f"{issue['type']} → {action['key']}"
            assert action["label"] == ACTION_LABELS[action["key"]]


def test_action_item_selection_is_recorded_without_changing_values(confirmed, client):
    """조치사항 선택은 의사결정 기록이며 확정값을 바꾸지 않는다."""
    issues = client.get(f"/api/engagements/{confirmed}/issues").json()
    action_item = next(i for i in issues if i["type"] == "wip_action")
    before = client.get(f"/api/engagements/{confirmed}/pnl").json()

    response = client.post(
        f"/api/issues/{action_item['id']}/resolve",
        json={"selected_action": "request_change_order", "actor": "EP"},
    )
    assert response.status_code == 200, response.text

    after = client.get(f"/api/engagements/{confirmed}/pnl").json()
    assert after["cumulative_usage"] == before["cumulative_usage"]
    assert after["ltd_required"] == before["ltd_required"]

    resolved = next(
        i
        for i in client.get(f"/api/engagements/{confirmed}/issues").json()
        if i["id"] == action_item["id"]
    )
    assert resolved["status"] == "resolved"
    assert resolved["selected_action"] == "request_change_order"
    assert resolved["resolved_at"] is not None


def test_keep_current_wbs_leaves_values_unchanged(confirmed, client):
    issues = client.get(f"/api/engagements/{confirmed}/issues").json()
    issue = next(i for i in issues if i["type"] == "wbs_attribution")
    result = client.post(
        f"/api/issues/{issue['id']}/resolve",
        json={"selected_action": "keep_current_wbs", "actor": "EP"},
    ).json()
    before = {row["code"]: row["ltd_required"] for row in result["before"]["wbs"]}
    after = {row["code"]: row["ltd_required"] for row in result["after"]["wbs"]}
    assert before == after


def test_exclude_temporarily_removes_amount_from_calculation(confirmed, client):
    issues = client.get(f"/api/engagements/{confirmed}/issues").json()
    issue = next(i for i in issues if i["type"] == "wbs_attribution")
    result = client.post(
        f"/api/issues/{issue['id']}/resolve",
        json={"selected_action": "exclude_temporarily", "actor": "EP"},
    ).json()
    after = {row["code"]: row["cumulative_usage"] for row in result["after"]["wbs"]}
    # 1차 WBS에서 11~12월 발생액 9,895,867원이 빠진다
    assert after["KOR01434-01-01"] == 269_962_247
    assert after[WBS_2] == 77_629_160


def test_reassign_requires_target_and_rejects_unknown_action(confirmed, client):
    issues = client.get(f"/api/engagements/{confirmed}/issues").json()
    issue = next(i for i in issues if i["type"] == "wbs_attribution")

    missing_target = client.post(
        f"/api/issues/{issue['id']}/resolve", json={"selected_action": "reassign_to_next_wbs"}
    )
    assert missing_target.status_code == 422

    unknown = client.post(
        f"/api/issues/{issue['id']}/resolve", json={"selected_action": "do_something_else"}
    )
    assert unknown.status_code == 422
    assert "지원하지 않는 조치" in unknown.json()["detail"]


def test_wbs_attribution_actions_are_exactly_four():
    assert len(WBS_ATTRIBUTION_ACTIONS) == 4
    assert all(action in ACTION_LABELS for action in WBS_ATTRIBUTION_ACTIONS)


def test_resolved_action_item_keeps_decision_but_refreshes_numbers(confirmed, client):
    """조치를 선택한 건은 조건이 남아 있어도 재오픈하지 않되 수치는 갱신한다."""
    issues = client.get(f"/api/engagements/{confirmed}/issues").json()
    action_item = next(i for i in issues if i["type"] == "billing_action")
    client.post(
        f"/api/issues/{action_item['id']}/resolve",
        json={"selected_action": "issue_invoice", "actor": "EP"},
    )
    # 조치사항 재계산을 여러 번 수행해도 선택 기록이 유지된다
    for _ in range(2):
        client.post(f"/api/engagements/{confirmed}/action-items")
    refreshed = next(
        i
        for i in client.get(f"/api/engagements/{confirmed}/issues").json()
        if i["id"] == action_item["id"]
    )
    assert refreshed["status"] == "resolved"
    assert refreshed["selected_action"] == "issue_invoice"
    assert "미청구액" in refreshed["title"]

    # 조건 자체는 대시보드의 조치 필요 프로젝트로 계속 노출된다
    dashboard = client.get("/api/dashboard").json()
    action = next(a for a in dashboard["action_required"] if a["engagement_id"] == confirmed)
    assert any("LTD" in reason or "손실" in reason for reason in action["reasons"])
