"""캡처 업로드 처리(§FR-02)."""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config
from ..enums import ScreenType, UploadStatus
from ..models import Engagement, Upload
from ..ocr.classifier import classify
from . import audit

ALLOWED_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}

#: 확장자를 믿지 않고 실제 바이트로 이미지 형식을 확인한다.
MAGIC_SIGNATURES: tuple[tuple[bytes, str], ...] = (
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"\xff\xd8\xff", "jpeg"),
)


def _looks_like_image(content: bytes) -> bool:
    if any(content.startswith(magic) for magic, _ in MAGIC_SIGNATURES):
        return True
    # WEBP: RIFF....WEBP
    return content[:4] == b"RIFF" and content[8:12] == b"WEBP"


class UploadError(ValueError):
    pass


def image_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def store_upload(
    session: Session,
    *,
    engagement: Engagement,
    filename: str,
    content: bytes,
    screen_type: str | None = None,
    uploaded_by: str | None = None,
) -> tuple[Upload, bool]:
    """이미지를 저장하고 Upload를 생성한다.

    동일 해시가 이미 있으면 기존 Upload를 반환하고 중복 경고를 남긴다
    (자동 확정하지 않는다, §12.2-7). 두 번째 반환값은 중복 여부다.
    """
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise UploadError(f"지원하지 않는 형식입니다: {suffix or filename} (PNG·JPG·WEBP)")
    if not content:
        raise UploadError("빈 파일입니다.")
    if len(content) > config.MAX_UPLOAD_BYTES:
        limit_mb = config.MAX_UPLOAD_BYTES / (1024 * 1024)
        raise UploadError(
            f"파일이 너무 큽니다({len(content) / (1024 * 1024):.1f}MB). "
            f"{limit_mb:.0f}MB 이하로 캡처하십시오."
        )
    if not _looks_like_image(content):
        raise UploadError(
            "이미지 파일로 인식되지 않습니다. 확장자를 바꾼 다른 형식의 파일인지 확인하십시오."
        )

    digest = image_hash(content)
    existing = session.execute(
        select(Upload).where(
            Upload.engagement_id == engagement.id, Upload.image_hash == digest
        )
    ).scalars().first()

    resolved_type, source = classify(user_choice=screen_type, filename=filename)

    if existing is not None:
        warnings = list(existing.warnings or [])
        message = (
            f"동일 이미지 해시({digest[:12]}…)가 이미 업로드되어 있습니다"
            f"(Upload #{existing.id}, {existing.uploaded_at:%Y-%m-%d %H:%M}). "
            "중복 업로드로 판정해 기존 업로드에 연결했으며 자동 확정하지 않습니다."
        )
        if message not in warnings:
            warnings.append(message)
        existing.warnings = warnings
        audit.log(
            session,
            entity="upload",
            entity_id=existing.id,
            field="duplicate_upload",
            after=digest,
            actor=uploaded_by,
        )
        return existing, True

    config.ensure_dirs()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    safe_name = f"{engagement.engagement_code}-{stamp}-{digest[:8]}{suffix}"
    target = config.UPLOAD_DIR / safe_name
    target.write_bytes(content)

    upload = Upload(
        engagement_id=engagement.id,
        file_path=str(target),
        original_filename=filename,
        image_hash=digest,
        screen_type=resolved_type.value,
        screen_type_source=source,
        uploaded_by=uploaded_by,
        status=UploadStatus.UPLOADED.value,
        warnings=[],
    )
    session.add(upload)
    session.flush()
    audit.log(
        session,
        entity="upload",
        entity_id=upload.id,
        field="status",
        after=UploadStatus.UPLOADED.value,
        actor=uploaded_by,
    )
    return upload, False


def set_screen_type(session: Session, upload: Upload, screen_type: str, actor: str | None = None) -> Upload:
    """사용자가 화면 유형을 확정한다(자동 분류 결과 확인)."""
    before = upload.screen_type
    upload.screen_type = ScreenType(screen_type).value
    upload.screen_type_source = "user"
    audit.log(
        session,
        entity="upload",
        entity_id=upload.id,
        field="screen_type",
        before=before,
        after=upload.screen_type,
        actor=actor,
    )
    return upload
