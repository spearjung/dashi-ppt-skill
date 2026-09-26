"""공용 비밀번호 인증(웹 배포용)."""

from __future__ import annotations

import importlib
import time

import pytest
from fastapi.testclient import TestClient

PASSWORD = "test-password-1234"


@pytest.fixture()
def secure_client(session, monkeypatch):
    """인증이 켜진 앱. config를 다시 읽어야 하므로 모듈을 재적재한다."""
    monkeypatch.setenv("PNL_APP_PASSWORD", PASSWORD)
    monkeypatch.setenv("PNL_AUTH_ENABLED", "1")

    from app import auth, config

    importlib.reload(config)
    importlib.reload(auth)

    import app.api.auth as api_auth
    import app.api.deps as deps
    import app.main as main

    importlib.reload(api_auth)
    importlib.reload(deps)
    importlib.reload(main)

    from app.db import get_session

    def _override():
        yield session

    main.app.dependency_overrides[get_session] = _override
    with TestClient(main.app) as client:
        yield client
    main.app.dependency_overrides.clear()

    # 다른 테스트에 영향을 주지 않도록 인증 없는 상태로 되돌린다
    monkeypatch.delenv("PNL_APP_PASSWORD", raising=False)
    monkeypatch.setenv("PNL_AUTH_ENABLED", "0")
    importlib.reload(config)
    importlib.reload(auth)
    importlib.reload(api_auth)
    importlib.reload(deps)
    importlib.reload(main)


def test_api_requires_login(secure_client):
    """인증이 켜지면 API는 로그인 없이 접근할 수 없다."""
    response = secure_client.get("/api/engagements")
    assert response.status_code == 401
    assert "로그인" in response.json()["detail"]


def test_health_and_session_are_public(secure_client):
    health = secure_client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["auth_required"] is True

    session = secure_client.get("/api/auth/session")
    assert session.status_code == 200
    assert session.json()["authenticated"] is False


def test_login_then_access(secure_client):
    login = secure_client.post(
        "/api/auth/login", json={"name": "정창모", "password": PASSWORD}
    )
    assert login.status_code == 200, login.text
    assert login.json() == {"authenticated": True, "name": "정창모", "auth_required": True}

    cookie = login.cookies.get("pnl_session")
    assert cookie, "세션 쿠키가 설정되지 않았습니다."
    set_cookie = login.headers["set-cookie"]
    assert "HttpOnly" in set_cookie
    assert "SameSite=lax" in set_cookie.lower() or "samesite=lax" in set_cookie.lower()

    assert secure_client.get("/api/engagements").status_code == 200
    assert secure_client.get("/api/auth/session").json()["name"] == "정창모"


def test_wrong_password_rejected(secure_client):
    response = secure_client.post(
        "/api/auth/login", json={"name": "EP", "password": "wrong-password"}
    )
    assert response.status_code == 401
    assert "비밀번호" in response.json()["detail"]
    assert secure_client.get("/api/engagements").status_code == 401


def test_logout_clears_session(secure_client):
    secure_client.post("/api/auth/login", json={"name": "EP", "password": PASSWORD})
    assert secure_client.get("/api/engagements").status_code == 200
    secure_client.post("/api/auth/logout")
    assert secure_client.get("/api/engagements").status_code == 401


def test_login_attempts_are_throttled(secure_client):
    from app import auth, config

    auth.throttle.reset("testclient")
    for _ in range(config.LOGIN_MAX_ATTEMPTS):
        secure_client.post("/api/auth/login", json={"name": "EP", "password": "nope"})
    blocked = secure_client.post(
        "/api/auth/login", json={"name": "EP", "password": PASSWORD}
    )
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers
    auth.throttle.reset("testclient")


def test_session_actor_is_recorded_not_client_supplied(secure_client, session):
    """확정 기록의 행위자는 세션 이름이며 요청 본문 값으로 위조할 수 없다."""
    from tests.conftest import make_png
    from tests.fixtures_kor01434 import CAPTURE_A, ENGAGEMENT_PAYLOAD

    secure_client.post("/api/auth/login", json={"name": "정창모", "password": PASSWORD})
    engagement = secure_client.post("/api/engagements", json=ENGAGEMENT_PAYLOAD).json()
    upload = secure_client.post(
        f"/api/engagements/{engagement['id']}/uploads",
        files=[("files", ("cap.png", make_png(), "image/png"))],
    ).json()[0]["upload"]
    secure_client.post(f"/api/uploads/{upload['id']}/ocr-payload", json={"payload": CAPTURE_A})

    view = secure_client.get(f"/api/uploads/{upload['id']}/verification").json()
    result = secure_client.post(
        f"/api/uploads/{upload['id']}/decisions",
        json={
            "decisions": [{"ocr_record_id": r["id"], "action": "confirm"} for r in view["records"]],
            # 본문으로 다른 이름을 보내도 세션 이름이 기록된다
            "actor": "누군가",
        },
    ).json()
    assert all(row["confirmed_by"] == "정창모" for row in result["confirmed"])


def test_session_expiry(monkeypatch):
    """만료된 세션 토큰은 거부된다."""
    monkeypatch.setenv("PNL_APP_PASSWORD", PASSWORD)
    monkeypatch.setenv("PNL_SESSION_HOURS", "0")
    from app import auth, config

    importlib.reload(config)
    importlib.reload(auth)
    token = auth.create_session("EP")
    time.sleep(1.1)
    assert auth.read_session(token) is None

    monkeypatch.delenv("PNL_SESSION_HOURS", raising=False)
    monkeypatch.delenv("PNL_APP_PASSWORD", raising=False)
    importlib.reload(config)
    importlib.reload(auth)


def test_short_password_refuses_startup(monkeypatch):
    """짧은 공용 비밀번호는 기동을 막는다."""
    monkeypatch.setenv("PNL_APP_PASSWORD", "short")
    monkeypatch.setenv("PNL_AUTH_ENABLED", "1")
    from app import config

    importlib.reload(config)
    assert config.AUTH_ENABLED is True
    with pytest.raises(config.ConfigError, match="너무 짧습니다"):
        config.validate()

    monkeypatch.delenv("PNL_APP_PASSWORD", raising=False)
    monkeypatch.setenv("PNL_AUTH_ENABLED", "0")
    importlib.reload(config)


def test_password_alone_enables_auth(monkeypatch):
    """PNL_AUTH_ENABLED를 주지 않아도 비밀번호가 있으면 인증이 켜진다."""
    monkeypatch.setenv("PNL_APP_PASSWORD", PASSWORD)
    monkeypatch.delenv("PNL_AUTH_ENABLED", raising=False)
    from app import config

    importlib.reload(config)
    assert config.AUTH_ENABLED is True
    # HTTPS 쿠키가 꺼져 있으면 경고하되 기동은 막지 않는다
    assert any("SECURE_COOKIES" in w for w in config.validate())

    monkeypatch.delenv("PNL_APP_PASSWORD", raising=False)
    monkeypatch.setenv("PNL_AUTH_ENABLED", "0")
    importlib.reload(config)


def test_auth_enabled_without_password_refuses_startup(monkeypatch):
    monkeypatch.delenv("PNL_APP_PASSWORD", raising=False)
    monkeypatch.setenv("PNL_AUTH_ENABLED", "1")
    from app import config

    importlib.reload(config)
    with pytest.raises(config.ConfigError, match="PNL_APP_PASSWORD"):
        config.validate()

    monkeypatch.setenv("PNL_AUTH_ENABLED", "0")
    importlib.reload(config)


def test_api_docs_are_protected(secure_client):
    """인증이 켜지면 API 명세도 익명으로 열람할 수 없다."""
    for path in ("/docs", "/openapi.json", "/redoc"):
        assert secure_client.get(path).status_code == 401, path

    secure_client.post("/api/auth/login", json={"name": "EP", "password": PASSWORD})
    assert secure_client.get("/openapi.json").status_code == 200


def test_static_path_traversal_falls_back_to_index(secure_client, tmp_path, monkeypatch):
    """정적 경로 이탈 요청은 파일을 노출하지 않는다."""
    # 인증이 켜진 상태에서도 SPA 진입점은 공개된다(로그인 화면을 보여주기 위함).
    response = secure_client.get("/../../etc/passwd")
    assert response.status_code in (200, 404)
    assert "root:" not in response.text


def test_wildcard_cors_is_refused(monkeypatch):
    """세션 쿠키를 쓰므로 모든 출처 허용은 기동을 막는다."""
    monkeypatch.setenv("PNL_CORS_ORIGINS", "*")
    from app import config

    importlib.reload(config)
    with pytest.raises(config.ConfigError, match="와일드카드"):
        config.validate()

    monkeypatch.delenv("PNL_CORS_ORIGINS", raising=False)
    importlib.reload(config)
