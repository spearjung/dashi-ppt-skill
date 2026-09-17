"""Phase 0 CLI 흐름(§11).

캡처 업로드 → 판독 → CSV 편집 → 확정 → HTML 리포트까지 한 번에 검증한다.
"""

from __future__ import annotations

import csv
import json

import pytest

from tests.conftest import make_png
from tests.fixtures_kor01434 import (
    CAPTURE_A,
    CAPTURE_B,
    ENGAGEMENT_PAYLOAD,
    LTD_WBS1_AFTER,
    LTD_WBS2_AFTER,
    WBS_1,
    WBS_2,
)


@pytest.fixture()
def workspace(tmp_path, monkeypatch, session):
    """CLI는 자체 세션을 열므로 테스트 DB 경로를 그대로 사용한다."""
    from app import cli

    monkeypatch.setattr(cli, "init_db", lambda: None)
    files = {
        "project.json": json.dumps(ENGAGEMENT_PAYLOAD, ensure_ascii=False),
        "a.ocr.json": json.dumps(CAPTURE_A, ensure_ascii=False),
        "b.ocr.json": json.dumps(CAPTURE_B, ensure_ascii=False),
    }
    for name, content in files.items():
        (tmp_path / name).write_text(content, encoding="utf-8")
    (tmp_path / "a.png").write_bytes(make_png(4, 4))
    (tmp_path / "b.png").write_bytes(make_png(5, 4))
    return tmp_path


def test_cli_end_to_end(workspace, capsys, session):
    from app import cli

    cli.main(["create-project", str(workspace / "project.json")])
    assert "KOR01434" in capsys.readouterr().out

    cli.main(
        [
            "ingest",
            "KOR01434",
            str(workspace / "a.png"),
            str(workspace / "b.png"),
            "--payload",
            str(workspace / "a.ocr.json"),
            str(workspace / "b.ocr.json"),
            "--actor",
            "EP",
        ]
    )
    out = capsys.readouterr().out
    assert "유형=wip" in out
    assert "이상징후=1건" in out  # 1차 WBS 귀속 오류

    csv_path = workspace / "rows.csv"
    cli.main(["export-csv", "KOR01434", str(csv_path)])
    rows = list(csv.DictReader(csv_path.open(newline="", encoding="utf-8-sig")))
    assert len(rows) == 8
    assert {r["confidence"] for r in rows} == {"high"}

    # CSV에서 1차 WBS의 11~12월 행을 2차 WBS로 재분류한다
    for row in rows:
        if row["wbs_code"] == WBS_1 and row["period_from"] == "2025-11-01":
            row["action"] = "reassign"
            row["wbs_code"] = WBS_2
    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    cli.main(["import-csv", "KOR01434", str(csv_path), "--actor", "EP"])
    assert "Snapshot" in capsys.readouterr().out

    report = workspace / "report.html"
    cli.main(["report", "KOR01434", str(report)])
    summary = capsys.readouterr().out
    assert "357,487,274원" in summary  # 누적 사용액
    assert "69,487,274원" in summary  # LTD 필요액

    html = report.read_text(encoding="utf-8")
    assert f"{LTD_WBS1_AFTER:,}" in html
    assert f"{LTD_WBS2_AFTER:,}" in html
    assert "잠정" in html  # Backlog 미입력
    assert "<table" in html and "시나리오" in html


def test_cli_rejects_unknown_engagement(workspace):
    from app import cli

    with pytest.raises(SystemExit):
        cli.main(["report", "NOPE", str(workspace / "x.html")])
