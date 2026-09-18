"""프로젝트 손익관리 프로그램 — FastAPI 진입점.

로컬 실행:
    uvicorn app.main:app --reload --port 8000

웹 배포(클라우드 호스팅):
    프런트엔드를 빌드해 두면 같은 오리진에서 SPA를 함께 서빙하므로 포트가 하나다.
    PNL_APP_PASSWORD를 설정해 인증을 켜고, HTTPS 뒤에 두고 PNL_SECURE_COOKIES=1로 둔다.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import auth, config
from .api import router
from .calc.formulas import FORMULA_VERSION
from .db import init_db

logger = logging.getLogger("pnl")

#: 인증 없이 접근 가능한 API 경로
PUBLIC_API_PATHS = frozenset(
    {
        "/api/health",
        "/api/auth/login",
        "/api/auth/logout",
        "/api/auth/session",
    }
)

#: API 명세 경로. 인증이 켜지면 함께 보호해 익명 노출 면적을 줄인다.
DOCS_PATHS = frozenset({"/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect"})


@asynccontextmanager
async def lifespan(_app: FastAPI):
    for warning in config.validate():
        logger.warning("설정 경고: %s", warning)
    init_db()
    logger.info(
        "기동 완료 — 인증 %s, 판독 엔진 %s, DB %s",
        "사용" if config.AUTH_ENABLED else "미사용",
        config.OCR_PROVIDER,
        "postgresql" if config.DATABASE_URL.startswith("postgres") else "sqlite",
    )
    yield


app = FastAPI(
    title="프로젝트 손익관리 프로그램",
    description=(
        "화면 캡처 업로드 → OCR 판독 → 사용자 검증·확정 → Snapshot → 손익 계산. "
        "OCR 판독값은 임시값이며 확정값만 손익 계산에 사용한다."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# 같은 오리진에서 SPA를 서빙하면 CORS가 필요 없다. 개발 중 별도 포트를 쓸 때만 쓰인다.
if config.CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.middleware("http")
async def security_and_auth(request: Request, call_next):
    """API 인증 검사와 보안 헤더 적용."""
    path = request.url.path

    needs_auth = config.AUTH_ENABLED and request.method != "OPTIONS" and (
        (path.startswith("/api/") and path not in PUBLIC_API_PATHS) or path in DOCS_PATHS
    )
    if needs_auth and auth.read_session(request.cookies.get(config.SESSION_COOKIE)) is None:
        return JSONResponse(
            {"detail": "로그인이 필요합니다."},
            status_code=401,
            headers=_security_headers(),
        )

    response = await call_next(request)
    for key, value in _security_headers().items():
        response.headers.setdefault(key, value)
    return response


def _security_headers() -> dict[str, str]:
    return {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "no-referrer",
        # 자체 자원만 허용한다. 외부 스크립트·폰트를 쓰지 않으므로 self로 충분하다.
        "Content-Security-Policy": (
            "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
            "script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'"
        ),
    }


app.include_router(router)


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "formula_version": FORMULA_VERSION,
        "ocr_provider": config.OCR_PROVIDER,
        "currency": config.DEFAULT_CURRENCY,
        "auth_required": config.AUTH_ENABLED,
        "offline_capable": True,
    }


# ── SPA 서빙 ────────────────────────────────────────────────────────────────
# 빌드 산출물이 있으면 같은 오리진에서 프런트엔드를 제공한다. 없으면 API 전용으로 동작한다.
_INDEX = config.STATIC_DIR / "index.html"

if _INDEX.exists():
    _ASSETS = config.STATIC_DIR / "assets"
    if _ASSETS.is_dir():
        app.mount("/assets", StaticFiles(directory=_ASSETS), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        """클라이언트 라우팅 경로는 모두 index.html로 되돌린다."""
        if full_path.startswith("api/"):
            raise HTTPException(404, "API 경로를 찾을 수 없습니다.")
        candidate = (config.STATIC_DIR / full_path).resolve()
        # 경로 이탈 방지 — 정적 디렉터리 밖 파일은 제공하지 않는다.
        if (
            full_path
            and candidate.is_file()
            and candidate.is_relative_to(config.STATIC_DIR.resolve())
        ):
            return FileResponse(candidate)
        return FileResponse(_INDEX)
