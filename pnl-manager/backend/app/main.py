"""프로젝트 손익관리 프로그램 — FastAPI 진입점.

로컬 실행 전제(§8.1):
    uvicorn app.main:app --reload --port 8000
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import config
from .api import router
from .calc.formulas import FORMULA_VERSION
from .db import init_db

app = FastAPI(
    title="프로젝트 손익관리 프로그램",
    description=(
        "화면 캡처 업로드 → OCR 판독 → 사용자 검증·확정 → Snapshot → 손익 계산. "
        "OCR 판독값은 임시값이며 확정값만 손익 계산에 사용한다."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.on_event("startup")
def _startup() -> None:
    init_db()


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "formula_version": FORMULA_VERSION,
        "ocr_provider": config.OCR_PROVIDER,
        "currency": config.DEFAULT_CURRENCY,
        "offline_capable": True,
    }
