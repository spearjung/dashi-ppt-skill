"""금액 단위 인식·정규화(§FR-03, §9 단위 일관성).

저장은 항상 원(KRW) 정수 단위로 통일한다. 단위가 화면에 표시되지 않은 경우
곱수를 임의로 가정하지 않고 unit=None으로 두어 신뢰도 Low를 유도한다.
"""

from __future__ import annotations

import re

#: 화면 표기 → (표준 단위 코드, 원 단위 곱수)
UNIT_TABLE: dict[str, tuple[str, int]] = {
    "원": ("KRW", 1),
    "krw": ("KRW", 1),
    "won": ("KRW", 1),
    "천원": ("KRW_THOUSAND", 1_000),
    "천 원": ("KRW_THOUSAND", 1_000),
    "in thousands": ("KRW_THOUSAND", 1_000),
    "백만원": ("KRW_MILLION", 1_000_000),
    "백만 원": ("KRW_MILLION", 1_000_000),
    "in millions": ("KRW_MILLION", 1_000_000),
    "억원": ("KRW_100M", 100_000_000),
}

MULTIPLIER: dict[str, int] = {
    "KRW": 1,
    "KRW_THOUSAND": 1_000,
    "KRW_MILLION": 1_000_000,
    "KRW_100M": 100_000_000,
}

_UNIT_HINT = re.compile(r"\(?\s*(단위\s*[:：]?\s*)?(원|천\s?원|백만\s?원|억원|KRW|in thousands|in millions)\s*\)?", re.I)
_NUMBER = re.compile(r"^[\s ]*([(\-+]?)\s*([0-9][0-9,\.\s ]*)\s*\)?\s*$")
_TRUNCATION = re.compile(r"(\.\.\.|…|#{2,}|\*{2,})")


class UnitParseError(ValueError):
    """숫자·단위를 신뢰할 수 있게 해석하지 못한 경우."""


def detect_unit(text: str | None) -> str | None:
    """표 제목·열 제목 등 문자열에서 금액 단위를 추출한다.

    단위 표기를 찾지 못하면 None을 반환한다(§FR-03 단위 미표시 → 신뢰도 Low).
    """
    if not text:
        return None
    match = _UNIT_HINT.search(text)
    if not match:
        return None
    token = re.sub(r"\s+", "", match.group(2)).lower()
    for key, (code, _mult) in UNIT_TABLE.items():
        if re.sub(r"\s+", "", key).lower() == token:
            return code
    return None


def is_truncated(raw: str | None) -> bool:
    """숫자 잘림(…, ###) 흔적 여부."""
    return bool(raw) and bool(_TRUNCATION.search(raw))


def parse_number(raw: str | int | float | None) -> float:
    """화면 표기 문자열을 수치로 변환한다.

    괄호 표기(1,234) 및 선행 부호는 음수로 해석한다.
    """
    if raw is None or raw == "":
        raise UnitParseError("빈 값")
    if isinstance(raw, (int, float)):
        return float(raw)
    text = str(raw).strip().replace(" ", " ")
    text = _UNIT_HINT.sub("", text).strip()
    negative = text.startswith("(") and text.endswith(")")
    if negative:
        text = text[1:-1].strip()
    if is_truncated(text):
        raise UnitParseError(f"숫자 잘림 의심: {raw!r}")
    match = _NUMBER.match(text)
    if not match:
        raise UnitParseError(f"숫자로 해석 불가: {raw!r}")
    sign = -1.0 if negative or match.group(1) == "-" else 1.0
    body = re.sub(r"[,\s ]", "", match.group(2))
    if body.count(".") > 1:
        raise UnitParseError(f"소수점 중복: {raw!r}")
    return sign * float(body)


def normalize_amount(raw: str | int | float | None, unit: str | None) -> int:
    """금액을 원(KRW) 정수로 정규화한다.

    unit이 None이면 곱수를 가정하지 않고 원 단위로 취급하되, 호출 측에서
    신뢰도 Low 처리를 하도록 unit 미확정 사실을 별도로 보존해야 한다.
    """
    value = parse_number(raw)
    multiplier = MULTIPLIER.get(unit or "KRW", 1)
    return int(round(value * multiplier))


def format_krw(amount: int | None) -> str:
    """표시용 원 단위 포맷."""
    if amount is None:
        return "-"
    return f"{amount:,}원"
