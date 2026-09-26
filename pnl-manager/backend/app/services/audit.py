"""감사 추적(§9). 모든 확정·수정·제외·재분류를 전후 값과 함께 기록한다."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ..models import AuditLog


def log(
    session: Session,
    *,
    entity: str,
    entity_id: int | None,
    field: str | None = None,
    before: Any = None,
    after: Any = None,
    actor: str | None = None,
) -> AuditLog:
    entry = AuditLog(
        entity=entity,
        entity_id=entity_id,
        field=field,
        before=None if before is None else str(before),
        after=None if after is None else str(after),
        actor=actor,
    )
    session.add(entry)
    return entry
