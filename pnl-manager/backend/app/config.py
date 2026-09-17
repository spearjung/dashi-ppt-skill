"""애플리케이션 설정.

로컬 실행(§8.1)을 전제로 하며 모든 경로는 프로젝트 루트의 data/ 아래에 둔다.
외부 LLM API 사용 여부는 환경변수로만 전환되며 기본값은 오프라인(manual)이다(§9 가용성).
"""

from __future__ import annotations

import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent


def _env_path(key: str, default: Path) -> Path:
    raw = os.environ.get(key)
    return Path(raw).expanduser().resolve() if raw else default


DATA_DIR = _env_path("PNL_DATA_DIR", PROJECT_ROOT / "data")
UPLOAD_DIR = DATA_DIR / "uploads"
DB_PATH = _env_path("PNL_DB_PATH", DATA_DIR / "db.sqlite")
DATABASE_URL = os.environ.get("PNL_DATABASE_URL") or f"sqlite:///{DB_PATH}"

# ocr 판독 엔진: manual(오프라인 직접입력) | claude(Claude Vision API) | fixture(테스트)
OCR_PROVIDER = os.environ.get("PNL_OCR_PROVIDER", "manual")
OCR_MODEL = os.environ.get("PNL_OCR_MODEL", "claude-opus-5")
# WBS Code·고객사명 마스킹 옵션(§8.2)
OCR_MASK_SENSITIVE = os.environ.get("PNL_OCR_MASK", "0") not in ("0", "", "false", "False")

# 기본 통화. 저장은 항상 원(KRW) 정수 단위(§9 단위 일관성).
DEFAULT_CURRENCY = os.environ.get("PNL_CURRENCY", "KRW")

# 조치사항 자동 등록 기준치(§FR-12)
UNBILLED_THRESHOLD = int(os.environ.get("PNL_UNBILLED_THRESHOLD", "50000000"))

CORS_ORIGINS = [
    o.strip()
    for o in os.environ.get(
        "PNL_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if o.strip()
]


def ensure_dirs() -> None:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
