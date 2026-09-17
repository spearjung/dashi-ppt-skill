"""라우터 공통 의존성."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Path
from sqlalchemy.orm import Session

from ..db import get_session
from ..models import Engagement, Issue, Snapshot, Upload, Wbs


def db() -> Session:  # pragma: no cover - FastAPI 의존성 래퍼
    raise NotImplementedError


def get_engagement(
    engagement_id: int = Path(..., ge=1), session: Session = Depends(get_session)
) -> Engagement:
    engagement = session.get(Engagement, engagement_id)
    if engagement is None:
        raise HTTPException(404, f"Engagement #{engagement_id}를 찾을 수 없습니다.")
    return engagement


def get_upload(
    upload_id: int = Path(..., ge=1), session: Session = Depends(get_session)
) -> Upload:
    upload = session.get(Upload, upload_id)
    if upload is None:
        raise HTTPException(404, f"Upload #{upload_id}를 찾을 수 없습니다.")
    return upload


def get_issue(issue_id: int = Path(..., ge=1), session: Session = Depends(get_session)) -> Issue:
    issue = session.get(Issue, issue_id)
    if issue is None:
        raise HTTPException(404, f"Issue #{issue_id}를 찾을 수 없습니다.")
    return issue


def get_snapshot(
    snapshot_id: int = Path(..., ge=1), session: Session = Depends(get_session)
) -> Snapshot:
    snapshot = session.get(Snapshot, snapshot_id)
    if snapshot is None:
        raise HTTPException(404, f"Snapshot #{snapshot_id}를 찾을 수 없습니다.")
    return snapshot
