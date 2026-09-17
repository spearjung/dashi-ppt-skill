"""FastAPI 라우터."""

from fastapi import APIRouter

from . import analytics, auth, engagements, uploads, verify

router = APIRouter(prefix="/api")
router.include_router(auth.router)
router.include_router(engagements.router)
router.include_router(uploads.router)
router.include_router(verify.router)
router.include_router(analytics.router)

__all__ = ["router"]
