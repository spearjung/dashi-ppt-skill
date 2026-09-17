"""화면 유형 자동 분류(§FR-02).

사용자 선택을 우선하고, 미선택 시 판독기가 제시한 screen_type과 표 제목
키워드 기반 분류를 결합한다. 분류 결과는 사용자 확인 대상이다.
"""

from __future__ import annotations

from ..enums import ScreenType

#: 화면 유형별 판별 키워드(한글·영문 혼용 화면 대응)
KEYWORDS: dict[ScreenType, tuple[str, ...]] = {
    ScreenType.WIP: ("work in progress", "wip", "미청구", "net revenue"),
    ScreenType.LTD_ADJUSTMENT: ("ltd", "adjustment", "상각", "조정"),
    ScreenType.BILLING: ("billing", "invoice", "청구", "수금"),
    ScreenType.EXPENSE: ("expense", "outside service", "경비", "외주", "os"),
    ScreenType.TIME: ("time", "timesheet", "투입시간", "공수"),
    ScreenType.BACKLOG: ("backlog", "잔여", "remaining"),
    ScreenType.STAFFING: ("staffing", "resource", "투입계획", "인력"),
    ScreenType.CONTRACT_INFO: ("contract", "계약", "interlock", "engagement info"),
}

#: 키워드 충돌 시 우선순위. 구체적인 화면을 먼저 판정한다.
PRIORITY: tuple[ScreenType, ...] = (
    ScreenType.LTD_ADJUSTMENT,
    ScreenType.WIP,
    ScreenType.BILLING,
    ScreenType.BACKLOG,
    ScreenType.STAFFING,
    ScreenType.EXPENSE,
    ScreenType.TIME,
    ScreenType.CONTRACT_INFO,
)


def classify(
    *,
    user_choice: str | None = None,
    payload_screen_type: str | None = None,
    screen_title: str | None = None,
    filename: str | None = None,
) -> tuple[ScreenType, str]:
    """(화면 유형, 결정 근거) 를 반환한다.

    근거는 'user' | 'ocr' | 'title' | 'filename' | 'default' 중 하나이며
    user 이외의 값은 사용자 확인이 필요함을 뜻한다(§FR-02).
    """
    if user_choice:
        try:
            return ScreenType(user_choice), "user"
        except ValueError:
            pass

    if payload_screen_type:
        try:
            resolved = ScreenType(payload_screen_type)
            if resolved is not ScreenType.OTHER:
                return resolved, "ocr"
        except ValueError:
            pass

    for source, text in (("title", screen_title), ("filename", filename)):
        matched = _match_keywords(text)
        if matched:
            return matched, source

    return ScreenType.OTHER, "default"


def _match_keywords(text: str | None) -> ScreenType | None:
    if not text:
        return None
    lowered = text.lower()
    for screen in PRIORITY:
        for keyword in KEYWORDS[screen]:
            if keyword in lowered:
                return screen
    return None
