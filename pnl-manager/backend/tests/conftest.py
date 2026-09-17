"""테스트 공통 설정. 앱 import 전에 임시 DB·데이터 경로를 지정한다."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

_TMP = Path(tempfile.mkdtemp(prefix="pnl-test-"))
os.environ.setdefault("PNL_DATA_DIR", str(_TMP))
os.environ["PNL_DATABASE_URL"] = f"sqlite:///{_TMP / 'test.sqlite'}"
os.environ["PNL_OCR_PROVIDER"] = "fixture"

from app import config  # noqa: E402
from app.db import SessionLocal, engine  # noqa: E402
from app.models import Base  # noqa: E402


@pytest.fixture()
def session():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    config.ensure_dirs()
    db = SessionLocal()
    try:
        yield db
        db.commit()
    finally:
        db.close()


@pytest.fixture()
def client(session):
    from fastapi.testclient import TestClient

    from app.db import get_session
    from app.main import app

    def _override():
        yield session

    app.dependency_overrides[get_session] = _override
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def make_png(width: int = 4, height: int = 4) -> bytes:
    """테스트용 최소 PNG를 생성한다(업로드 경로·해시 검증 목적)."""
    import struct
    import zlib

    raw = b"".join(b"\x00" + b"\xff\xff\xff" * width for _ in range(height))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


@pytest.fixture()
def png_bytes() -> bytes:
    return make_png()


@pytest.fixture()
def png_bytes_alt() -> bytes:
    """해시가 다른 두 번째 캡처."""
    return make_png(5, 4)
