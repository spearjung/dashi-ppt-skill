"""로그인·로그아웃 API(공용 비밀번호)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from .. import auth, config

router = APIRouter(tags=["auth"])


class LoginIn(BaseModel):
    #: 확정·수정 기록에 남길 행위자 이름
    name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)


class SessionOut(BaseModel):
    authenticated: bool
    name: str | None = None
    auth_required: bool = True


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.post("/auth/login", response_model=SessionOut)
def login(payload: LoginIn, request: Request, response: Response):
    if not config.AUTH_ENABLED:
        return SessionOut(authenticated=True, name=payload.name, auth_required=False)

    key = _client_key(request)
    retry_after = auth.throttle.blocked(key)
    if retry_after:
        raise HTTPException(
            429,
            f"로그인 시도가 너무 많습니다. {retry_after}초 후 다시 시도하십시오.",
            headers={"Retry-After": str(retry_after)},
        )

    if not auth.verify_password(payload.password):
        auth.throttle.record_failure(key)
        raise HTTPException(401, "비밀번호가 올바르지 않습니다.")

    auth.throttle.reset(key)
    response.set_cookie(
        config.SESSION_COOKIE,
        auth.create_session(payload.name),
        max_age=config.SESSION_HOURS * 3600,
        httponly=True,
        samesite="lax",
        secure=config.SECURE_COOKIES,
        path="/",
    )
    return SessionOut(authenticated=True, name=payload.name.strip())


@router.post("/auth/logout", response_model=SessionOut)
def logout(response: Response):
    response.delete_cookie(config.SESSION_COOKIE, path="/")
    return SessionOut(authenticated=False, auth_required=config.AUTH_ENABLED)


@router.get("/auth/session", response_model=SessionOut)
def session(request: Request):
    if not config.AUTH_ENABLED:
        return SessionOut(authenticated=True, name=None, auth_required=False)
    name = auth.read_session(request.cookies.get(config.SESSION_COOKIE))
    return SessionOut(authenticated=name is not None, name=name)
