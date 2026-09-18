"""공용 비밀번호 기반 인증(웹 배포용).

설계
  - 비밀번호는 하나이고, 사용자는 로그인 시 자기 이름을 함께 입력한다.
    이름은 세션에 담겨 확정·수정 기록(confirmed_by, AuditLog.actor)의 행위자가 되므로
    비밀번호를 공용으로 쓰면서도 감사 추적(§9)이 유지된다.
  - 세션은 서버 상태 없이 서명된 쿠키로 유지한다(HMAC-SHA256).
  - 무차별 대입을 막기 위해 IP별 로그인 시도 횟수를 제한한다.

비밀번호를 확인한다는 것 외에 사용자를 식별하지는 않으므로, 이름은 자기 신고값이다.
개인별 책임 추적이 필요하면 사용자별 계정으로 전환해야 한다.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass, field

from . import config


def _secret() -> bytes:
    """세션 서명 키. 미설정 시 비밀번호에서 파생해 재시작 후에도 세션을 유지한다."""
    if config.SECRET_KEY:
        return config.SECRET_KEY.encode("utf-8")
    base = (config.APP_PASSWORD or "insecure-dev-secret").encode("utf-8")
    return hashlib.sha256(b"pnl-session-key:" + base).digest()


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _unb64(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def verify_password(candidate: str) -> bool:
    """비밀번호를 상수 시간으로 비교한다."""
    if not config.APP_PASSWORD:
        return False
    return hmac.compare_digest(candidate.encode("utf-8"), config.APP_PASSWORD.encode("utf-8"))


def create_session(name: str) -> str:
    """서명된 세션 토큰을 만든다."""
    payload = {
        "name": name.strip()[:100] or "사용자",
        "exp": int(time.time()) + config.SESSION_HOURS * 3600,
    }
    body = _b64(json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
    signature = _b64(hmac.new(_secret(), body.encode("ascii"), hashlib.sha256).digest())
    return f"{body}.{signature}"


def read_session(token: str | None) -> str | None:
    """세션 토큰에서 행위자 이름을 꺼낸다. 위조·만료 시 None."""
    if not token or "." not in token:
        return None
    body, _, signature = token.rpartition(".")
    expected = _b64(hmac.new(_secret(), body.encode("ascii"), hashlib.sha256).digest())
    if not hmac.compare_digest(signature, expected):
        return None
    try:
        payload = json.loads(_unb64(body))
    except (ValueError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or int(payload.get("exp", 0)) < time.time():
        return None
    name = payload.get("name")
    return name if isinstance(name, str) and name else None


@dataclass
class LoginThrottle:
    """IP별 로그인 실패 횟수 제한. 단일 프로세스 메모리에만 유지한다."""

    attempts: dict[str, list[float]] = field(default_factory=dict)

    def _recent(self, key: str, now: float) -> list[float]:
        window = now - config.LOGIN_WINDOW_SECONDS
        recent = [t for t in self.attempts.get(key, []) if t > window]
        self.attempts[key] = recent
        return recent

    def blocked(self, key: str) -> int:
        """차단 중이면 남은 대기 초, 아니면 0."""
        now = time.time()
        recent = self._recent(key, now)
        if len(recent) < config.LOGIN_MAX_ATTEMPTS:
            return 0
        return max(1, int(config.LOGIN_WINDOW_SECONDS - (now - min(recent))))

    def record_failure(self, key: str) -> None:
        now = time.time()
        self._recent(key, now)
        self.attempts.setdefault(key, []).append(now)

    def reset(self, key: str) -> None:
        self.attempts.pop(key, None)


throttle = LoginThrottle()
