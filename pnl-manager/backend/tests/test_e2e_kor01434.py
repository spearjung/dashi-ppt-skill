"""수용 기준 — KOR01434 E2E 시나리오(§12)."""

from __future__ import annotations

import pytest

from tests.fixtures_kor01434 import (
    CAPTURE_A,
    CAPTURE_B,
    ENGAGEMENT_PAYLOAD,
    LTD_WBS1_AFTER,
    LTD_WBS1_BEFORE,
    LTD_WBS2_AFTER,
    LTD_WBS2_BEFORE,
    RECLASSIFIED_AMOUNT,
    WBS_1,
    WBS_2,
)


def _create_engagement(client) -> dict:
    response = client.post("/api/engagements", json=ENGAGEMENT_PAYLOAD)
    assert response.status_code == 201, response.text
    return response.json()


def _upload(client, engagement_id: int, content: bytes, filename: str) -> dict:
    response = client.post(
        f"/api/engagements/{engagement_id}/uploads",
        files=[("files", (filename, content, "image/png"))],
        data={"uploaded_by": "EP"},
    )
    assert response.status_code == 201, response.text
    return response.json()[0]


def _confirm_all(client, upload_id: int, *, exclude_record_ids: set[int] | None = None) -> dict:
    """검증 화면의 모든 값을 '확인' 처리한다."""
    view = client.get(f"/api/uploads/{upload_id}/verification").json()
    decisions = [
        {"ocr_record_id": r["id"], "action": "confirm"}
        for r in view["records"]
        if r["id"] not in (exclude_record_ids or set())
    ]
    response = client.post(
        f"/api/uploads/{upload_id}/decisions", json={"decisions": decisions, "actor": "EP"}
    )
    assert response.status_code == 200, response.text
    return response.json()


def _wbs_ltd(pnl: dict, code: str) -> int:
    return next(w["ltd_required"] for w in pnl["wbs_results"] if w["code"] == code)


@pytest.fixture()
def scenario(client, png_bytes, png_bytes_alt):
    """§12.1 입력 — 두 캡처를 동시 업로드하고 판독 결과를 주입한다."""
    engagement = _create_engagement(client)
    eid = engagement["id"]

    upload_a = _upload(client, eid, png_bytes, "capture-wbs1.png")["upload"]
    upload_b = _upload(client, eid, png_bytes_alt, "capture-wbs2.png")["upload"]

    for upload, payload in ((upload_a, CAPTURE_A), (upload_b, CAPTURE_B)):
        response = client.post(
            f"/api/uploads/{upload['id']}/ocr-payload", json={"payload": payload}
        )
        assert response.status_code == 200, response.text

    return {"engagement": engagement, "upload_a": upload_a, "upload_b": upload_b}


def test_step1_both_captures_classified_as_wip(client, scenario):
    """§12.2-1 두 캡처가 각각 wip 유형으로 자동 분류된다."""
    for key in ("upload_a", "upload_b"):
        upload = client.get(f"/api/uploads/{scenario[key]['id']}").json()
        assert upload["screen_type"] == "wip"
        assert upload["screen_type_source"] in ("ocr", "title")
        assert upload["status"] == "ocr_done"
        assert upload["unit"] == "KRW"


def test_step2_wbs_attribution_issue_created(client, scenario):
    """§12.2-2 1차 계약기간 이후 발생액이 WBS 귀속 검토 Issue로 등록된다."""
    eid = scenario["engagement"]["id"]
    issues = client.get(f"/api/engagements/{eid}/issues").json()
    attribution = [i for i in issues if i["type"] == "wbs_attribution"]
    assert attribution, f"WBS 귀속 Issue가 없습니다: {issues}"

    detail = " ".join(i["detail"] for i in attribution)
    assert "8,030,000" in detail or "1,865,867" in detail
    assert WBS_2 in detail  # 재분류 대상 후보가 제시된다


def test_step3_four_suggested_actions(client, scenario):
    """§12.2-3 제안 조치 4종이 표시된다."""
    eid = scenario["engagement"]["id"]
    issues = client.get(f"/api/engagements/{eid}/issues").json()
    attribution = next(i for i in issues if i["type"] == "wbs_attribution")
    keys = [a["key"] for a in attribution["suggested_actions"]]
    assert keys == [
        "keep_current_wbs",
        "reassign_to_next_wbs",
        "check_duplicate_input",
        "exclude_temporarily",
    ]
    labels = [a["label"] for a in attribution["suggested_actions"]]
    assert labels == ["1차 WBS 유지", "2차 WBS로 재분류", "중복 입력 여부 확인", "계산 대상에서 임시 제외"]


def test_high_impact_fields_block_confirmation(client, scenario):
    """§12.3 고영향 필드(Time)는 개별 확인 전까지 확정이 차단된다(§FR-04·05)."""
    upload_id = scenario["upload_a"]["id"]
    view = client.get(f"/api/uploads/{upload_id}/verification").json()

    time_fields = [r for r in view["records"] if r["item_type"] == "time"]
    assert time_fields and all(r["high_impact"] for r in time_fields)
    assert all(r["needs_individual_confirmation"] for r in time_fields)
    assert view["gate"]["can_confirm"] is False
    assert view["gate"]["unconfirmed_fields"]

    blocked = client.post(f"/api/uploads/{upload_id}/confirm", json={"actor": "EP"})
    assert blocked.status_code == 409

    after = _confirm_all(client, upload_id)
    assert after["gate"]["can_confirm"] is True


def test_arithmetic_check_passes_for_capture_a(client, scenario):
    """§12.3 합계 9,895,867원이 자동검증을 통과한다(§FR-06)."""
    upload = client.get(f"/api/uploads/{scenario['upload_a']['id']}").json()
    log = upload["arithmetic_log"]
    assert log, "산술검증 로그가 없습니다."
    row2 = [c for c in log if c["row_index"] == 2 and c["rule"] == "time+expense+os=total"]
    assert row2 and row2[0]["passed"] is True
    assert row2[0]["actual"] == 9_895_867
    assert all(c["passed"] for c in log)


def _confirm_both(client, scenario) -> tuple[int, int]:
    eid = scenario["engagement"]["id"]
    snapshot_ids = []
    for key in ("upload_a", "upload_b"):
        upload_id = scenario[key]["id"]
        _confirm_all(client, upload_id)
        result = client.post(
            f"/api/uploads/{upload_id}/confirm", json={"actor": "EP", "create_snapshot": True}
        )
        assert result.status_code == 200, result.text
        snapshot_ids.append(result.json()["snapshot_id"])
    return eid, snapshot_ids


def test_step4_reclassification_recomputes_ltd(client, scenario):
    """§12.2-4·5 재분류 시 1차·2차 예상 LTD가 즉시 재계산되고 검산이 일치한다."""
    eid, _ = _confirm_both(client, scenario)

    before = client.get(f"/api/engagements/{eid}/pnl").json()
    assert _wbs_ltd(before, WBS_1) == LTD_WBS1_BEFORE
    assert _wbs_ltd(before, WBS_2) == LTD_WBS2_BEFORE

    issues = client.get(f"/api/engagements/{eid}/issues").json()
    issue = next(i for i in issues if i["type"] == "wbs_attribution")
    wbs_list = client.get(f"/api/engagements/{eid}/wbs").json()
    target = next(w["id"] for w in wbs_list if w["code"] == WBS_2)

    preview = client.get(
        f"/api/issues/{issue['id']}/reclassification-preview", params={"target_wbs_id": target}
    ).json()
    before_wbs = {w["code"]: w["ltd_required"] for w in preview["before"]["wbs"]}
    after_wbs = {w["code"]: w["ltd_required"] for w in preview["after"]["wbs"]}
    assert before_wbs[WBS_1] == LTD_WBS1_BEFORE
    assert before_wbs[WBS_2] == LTD_WBS2_BEFORE
    assert after_wbs[WBS_1] == LTD_WBS1_AFTER
    assert after_wbs[WBS_2] == LTD_WBS2_AFTER

    # §12.2-5 검산: 27,629,160 + 9,895,867 = 37,525,027
    assert LTD_WBS2_BEFORE + RECLASSIFIED_AMOUNT == LTD_WBS2_AFTER

    # 미리보기는 값을 바꾸지 않는다
    unchanged = client.get(f"/api/engagements/{eid}/pnl").json()
    assert _wbs_ltd(unchanged, WBS_1) == LTD_WBS1_BEFORE

    resolved = client.post(
        f"/api/issues/{issue['id']}/resolve",
        json={"selected_action": "reassign_to_next_wbs", "target_wbs_id": target, "actor": "EP"},
    )
    assert resolved.status_code == 200, resolved.text
    body = resolved.json()
    assert {w["code"]: w["ltd_required"] for w in body["after"]["wbs"]}[WBS_1] == LTD_WBS1_AFTER
    assert {w["code"]: w["ltd_required"] for w in body["after"]["wbs"]}[WBS_2] == LTD_WBS2_AFTER

    after = client.get(f"/api/engagements/{eid}/pnl").json()
    assert _wbs_ltd(after, WBS_1) == LTD_WBS1_AFTER
    assert _wbs_ltd(after, WBS_2) == LTD_WBS2_AFTER
    # 차수별 합계는 Engagement LTD 필요액과 일치한다
    assert after["ltd_required"] == LTD_WBS1_AFTER + LTD_WBS2_AFTER
    # 2차 LTD 조정액 10,000,000원이 반영되어 잔여 상각 필요액이 줄어든다
    wbs2 = next(w for w in after["wbs_results"] if w["code"] == WBS_2)
    assert wbs2["ltd_adjusted"] == 10_000_000
    assert wbs2["ltd_outstanding"] == LTD_WBS2_AFTER - 10_000_000


def test_step6_snapshots_preserved_before_and_after(client, scenario):
    """§12.2-6 재분류 전·후 Snapshot이 각각 보존되고 최신 기준일이 갱신된다."""
    eid, snapshot_ids = _confirm_both(client, scenario)
    issues = client.get(f"/api/engagements/{eid}/issues").json()
    issue = next(i for i in issues if i["type"] == "wbs_attribution")
    wbs_list = client.get(f"/api/engagements/{eid}/wbs").json()
    target = next(w["id"] for w in wbs_list if w["code"] == WBS_2)

    client.post(
        f"/api/issues/{issue['id']}/resolve",
        json={"selected_action": "reassign_to_next_wbs", "target_wbs_id": target, "actor": "EP"},
    )

    snapshots = client.get(f"/api/engagements/{eid}/snapshots").json()
    assert len(snapshots) >= 3  # 캡처 A 확정, 캡처 B 확정, 재분류 후
    assert all(s["formula_version"] == "1.0.0" for s in snapshots)

    # 재분류 전 Snapshot은 재분류 전 값을 그대로 재현한다(§9 재현성)
    pre = client.get(
        f"/api/engagements/{eid}/pnl", params={"snapshot_id": snapshot_ids[-1]}
    ).json()
    assert _wbs_ltd(pre, WBS_1) == LTD_WBS1_BEFORE
    assert _wbs_ltd(pre, WBS_2) == LTD_WBS2_BEFORE

    latest = snapshots[0]
    post = client.get(f"/api/engagements/{eid}/pnl", params={"snapshot_id": latest["id"]}).json()
    assert _wbs_ltd(post, WBS_1) == LTD_WBS1_AFTER

    dashboard = client.get("/api/dashboard").json()
    assert dashboard["latest_snapshot_as_of"] == "2025-12-31"
    project = next(p for p in dashboard["projects"] if p["engagement_id"] == eid)
    assert project["latest_snapshot_id"] == latest["id"]

    diff = client.get(f"/api/snapshots/{latest['id']}/diff").json()
    assert diff["previous_snapshot_id"] == snapshot_ids[-1]
    assert "items" in diff and "derived" in diff


def test_step7_reupload_same_image_is_flagged_duplicate(client, scenario, png_bytes):
    """§12.2-7 동일 캡처 재업로드는 해시 일치로 중복 경고되고 자동 확정되지 않는다."""
    eid = scenario["engagement"]["id"]
    result = _upload(client, eid, png_bytes, "capture-wbs1-again.png")
    assert result["duplicate"] is True
    assert result["upload"]["id"] == scenario["upload_a"]["id"]
    assert result["upload"]["status"] != "confirmed"
    assert any("동일 이미지 해시" in w for w in result["upload"]["warnings"])


def test_pnl_summary_matches_prd_figures(client, scenario):
    """프로젝트 손익 요약값이 §3.2 산식과 일치한다."""
    eid, _ = _confirm_both(client, scenario)
    pnl = client.get(f"/api/engagements/{eid}/pnl").json()

    assert pnl["total_contract_amount"] == 288_000_000
    # 누적 사용액 = 269,962,247 + 9,895,867 + 77,629,160
    assert pnl["cumulative_usage"] == 357_487_274
    assert pnl["contract_balance"] == 288_000_000 - 357_487_274
    # Backlog 미입력이므로 잔여 투입 예상액은 0이고 종료예상값은 잠정치다
    assert pnl["backlog_entered"] is False
    assert pnl["provisional"] is True
    assert pnl["eac"] == pnl["cumulative_usage"]
    assert pnl["final_expected_balance"] == 288_000_000 - 357_487_274
    assert any("Backlog 미입력" in w for w in pnl["warnings"])
    assert pnl["expected_margin_rate"] == round((288_000_000 - 357_487_274) / 288_000_000, 6)


def test_action_items_registered(client, scenario):
    """§FR-12 LTD 필요액·미청구액·Backlog 미입력 조치사항이 자동 등록된다."""
    eid, _ = _confirm_both(client, scenario)
    issues = client.get(f"/api/engagements/{eid}/issues").json()
    types = {i["type"] for i in issues}
    assert "wip_action" in types  # LTD 필요액 > 0
    assert "billing_action" in types  # 미청구액 > 기준치
    assert "backlog_missing" in types

    dashboard = client.get("/api/dashboard").json()
    action = next(a for a in dashboard["action_required"] if a["engagement_id"] == eid)
    assert action["severity"] == "high"
    assert any("LTD 필요액" in r for r in action["reasons"])
