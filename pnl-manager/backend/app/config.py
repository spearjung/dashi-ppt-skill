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

# ocr 판독 엔진: claude(Claude Vision API) | manual(오프라인 직접입력) | fixture(테스트)
# 캡처 이미지 외부 전송이 허용되어 claude를 기본값으로 둔다. 자격증명이 없으면
# 판독 시점에 안내 메시지를 반환하며, 검증 화면의 직접 입력으로 계속 진행할 수 있다.
OCR_PROVIDER = os.environ.get("PNL_OCR_PROVIDER", "claude")
OCR_MODEL = os.environ.get("PNL_OCR_MODEL", "claude-opus-5")
# WBS Code·고객사명 마스킹 옵션(§8.2)
OCR_MASK_SENSITIVE = os.environ.get("PNL_OCR_MASK", "0") not in ("0", "", "false", "False")

# 기본 통화. 저장은 항상 원(KRW) 정수 단위(§9 단위 일관성).
DEFAULT_CURRENCY = os.environ.get("PNL_CURRENCY", "KRW")

# 조치사항 자동 등록 기준치(§FR-12)
UNBILLED_THRESHOLD = int(os.environ.get("PNL_UNBILLED_THRESHOLD", "50000000"))

# ── 웹 배포 설정 ────────────────────────────────────────────────────────────
#: 공용 비밀번호. 설정되면 인증이 켜진다. 웹에 노출되는 배포에서는 필수다.
APP_PASSWORD = os.environ.get("PNL_APP_PASSWORD") or None
#: 비밀번호 최소 길이. 인터넷에 노출된 공용 비밀번호가 짧으면 무차별 대입에 취약하다.
MIN_PASSWORD_LENGTH = int(os.environ.get("PNL_MIN_PASSWORD_LENGTH", "12"))


def _flag(key: str, default: bool) -> bool:
    raw = os.environ.get(key)
    if raw is None:
        return default
    return raw.lower() not in ("0", "", "false", "no")


#: 인증 사용 여부. 기본은 '비밀번호가 설정되어 있으면 켜짐'.
AUTH_ENABLED = _flag("PNL_AUTH_ENABLED", APP_PASSWORD is not None)
#: 세션 쿠키 서명 키. 미설정 시 비밀번호에서 파생해 재시작 후에도 세션이 유지된다.
SECRET_KEY = os.environ.get("PNL_SECRET_KEY") or None
SESSION_HOURS = int(os.environ.get("PNL_SESSION_HOURS", "12"))
SESSION_COOKIE = "pnl_session"
#: HTTPS 전용 쿠키. 클라우드 호스팅(HTTPS)에서는 반드시 1로 둔다.
SECURE_COOKIES = _flag("PNL_SECURE_COOKIES", False)
#: 로그인 시도 제한 — 같은 IP에서 WINDOW초 동안 MAX회 실패하면 차단한다.
LOGIN_MAX_ATTEMPTS = int(os.environ.get("PNL_LOGIN_MAX_ATTEMPTS", "10"))
LOGIN_WINDOW_SECONDS = int(os.environ.get("PNL_LOGIN_WINDOW_SECONDS", "300"))

#: 업로드 1건 최대 크기. 화면 캡처는 통상 수백 KB이므로 넉넉한 상한이다.
MAX_UPLOAD_BYTES = int(os.environ.get("PNL_MAX_UPLOAD_BYTES", str(15 * 1024 * 1024)))

#: 빌드된 프런트엔드 경로. 존재하면 같은 오리진에서 SPA를 서빙한다.
STATIC_DIR = _env_path("PNL_STATIC_DIR", PROJECT_ROOT / "frontend" / "dist")

CORS_ORIGINS = [
    o.strip()
    for o in os.environ.get(
        "PNL_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if o.strip()
]


def ensure_dirs() -> None:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    if DATABASE_URL.startswith("sqlite"):
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)


class ConfigError(RuntimeError):
    """설정이 안전하지 않아 기동을 중단해야 하는 경우."""


def validate() -> list[str]:
    """기동 시 설정을 검증한다. 치명적 문제는 예외, 그 외는 경고로 반환한다."""
    warnings: list[str] = []

    if AUTH_ENABLED:
        if not APP_PASSWORD:
            raise ConfigError(
                "인증이 켜져 있으나 PNL_APP_PASSWORD가 없습니다. "
                "비밀번호를 설정하거나 PNL_AUTH_ENABLED=0으로 인증을 끄십시오."
            )
        if len(APP_PASSWORD) < MIN_PASSWORD_LENGTH:
            raise ConfigError(
                f"PNL_APP_PASSWORD가 너무 짧습니다({len(APP_PASSWORD)}자). "
                f"{MIN_PASSWORD_LENGTH}자 이상으로 설정하십시오."
            )
        if not SECURE_COOKIES:
            warnings.append(
                "PNL_SECURE_COOKIES가 꺼져 있습니다. HTTPS로 서비스한다면 1로 설정하십시오."
            )
    else:
        warnings.append(
            "인증이 꺼져 있습니다. 웹에 노출되는 환경이라면 PNL_APP_PASSWORD를 설정하십시오."
        )

    if OCR_PROVIDER == "claude" and not (
        os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
    ):
        warnings.append(
            "판독 엔진이 claude이지만 ANTHROPIC_API_KEY가 없습니다. "
            "자동 판독은 실패하고 검증 화면의 직접 입력만 가능합니다."
        )
    return warnings
