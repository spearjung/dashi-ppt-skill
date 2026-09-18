"""판독 엔진 어댑터.

- claude : 멀티모달 LLM + JSON 스키마 강제 출력(§8.1 권장)
- manual : 오프라인. 판독 없이 직접 입력 대기 상태로 둔다(§9 가용성)
- fixture: 이미지와 같은 경로의 `<파일명>.ocr.json` 을 판독 결과로 사용(테스트·수기 주입)

캡처 이미지는 외부로 전송되므로 claude 엔진은 명시적 환경변수 설정이 있을 때만
활성화되며, 마스킹 옵션(§8.2)이 켜져 있으면 WBS Code·고객사명을 판독 후 가린다.
"""

from __future__ import annotations

import base64
import json
import mimetypes
import re
from pathlib import Path
from typing import Protocol

from .. import config
from .schema import OCR_JSON_SCHEMA, OcrPayload

SYSTEM_PROMPT = """\
당신은 컨설팅 프로젝트 손익 시스템의 화면 캡처를 판독하는 OCR·표 구조 인식기입니다.
규칙:
1. 반드시 report_screen 도구를 한 번 호출해 결과를 전달하고, 자유 텍스트를 반환하지 않습니다.
2. 화면의 실제 항목명을 raw_label에 원문 그대로 보존합니다. 항목명을 번역·정규화하지 않습니다.
3. 하나의 화면에 여러 WBS 행이 있으면 행 단위로 분리합니다.
4. 금액 단위(원·천원·백만원)가 화면에 표시되지 않으면 unit을 null로 두고 추측하지 않습니다.
5. 숫자가 잘렸거나 커서·팝업에 가려졌으면 confidence를 low 또는 failed로 두고
   quality_warnings에 사유를 남깁니다. 가려진 필드는 obstructed=true로 표시합니다.
6. 누적값과 월 발생액을 구분해 value_basis에 cumulative / monthly / period 로 기록합니다.
7. 표 제목·열 제목·합계 행·조회 기준일·조회 기간·필터 조건을 함께 추출합니다.
8. 합계 행이 있으면 totals에 담고, time+expense+os=total 등 검산 결과를 arithmetic_checks에 남깁니다.
9. 판독한 값을 보정·반올림하지 않습니다. 화면에 보이는 숫자를 그대로 전달합니다.
"""

USER_PROMPT = """\
아래 캡처를 판독하십시오.
사용자가 지정한 화면 유형: {screen_type}
참고 WBS Code 목록: {wbs_codes}
"""


class OcrProviderError(RuntimeError):
    """판독 엔진 호출 실패. 호출 측에서 사용자 안내로 변환한다."""


class OcrProvider(Protocol):
    name: str

    def read(
        self, image_path: Path, *, screen_type: str | None = None, wbs_codes: list[str] | None = None
    ) -> OcrPayload: ...


class ManualProvider:
    """판독을 수행하지 않고 직접 입력 대기 상태를 만든다."""

    name = "manual"

    def read(
        self, image_path: Path, *, screen_type: str | None = None, wbs_codes: list[str] | None = None
    ) -> OcrPayload:
        return OcrPayload(
            screen_type=screen_type or "other",
            screen_title=None,
            rows=[],
            quality_warnings=[
                "판독 엔진이 manual로 설정되어 자동 판독을 수행하지 않았습니다. "
                "검증 화면에서 값을 직접 입력하십시오."
            ],
        )


class FixtureProvider:
    """이미지 옆의 `<파일명>.ocr.json` 을 판독 결과로 사용한다."""

    name = "fixture"

    def read(
        self, image_path: Path, *, screen_type: str | None = None, wbs_codes: list[str] | None = None
    ) -> OcrPayload:
        sidecar = image_path.with_suffix(image_path.suffix + ".ocr.json")
        if not sidecar.exists():
            return ManualProvider().read(image_path, screen_type=screen_type)
        data = json.loads(sidecar.read_text(encoding="utf-8"))
        return OcrPayload.model_validate(data)


class ClaudeVisionProvider:
    """Claude Vision + tool 스키마 강제 출력."""

    name = "claude"

    def __init__(self, model: str | None = None) -> None:
        self.model = model or config.OCR_MODEL

    def read(
        self, image_path: Path, *, screen_type: str | None = None, wbs_codes: list[str] | None = None
    ) -> OcrPayload:
        import anthropic  # 지연 import — 오프라인 환경 보호

        media_type = mimetypes.guess_type(image_path.name)[0] or "image/png"
        encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
        client = anthropic.Anthropic()
        try:
            response = client.messages.create(
                model=self.model,
                max_tokens=16000,
                system=SYSTEM_PROMPT,
                tools=[
                    {
                        "name": "report_screen",
                        "description": "판독한 화면 내용을 구조화해 보고한다.",
                        "input_schema": OCR_JSON_SCHEMA,
                        # 스키마를 정확히 만족하는 인자만 받는다(자유 텍스트 금지, §FR-03).
                        "strict": True,
                    }
                ],
                tool_choice={"type": "tool", "name": "report_screen"},
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": encoded,
                                },
                            },
                            {
                                "type": "text",
                                "text": USER_PROMPT.format(
                                    screen_type=screen_type or "미지정(자동 분류)",
                                    wbs_codes=", ".join(wbs_codes or []) or "없음",
                                ),
                            },
                        ],
                    }
                ],
            )
        except anthropic.RateLimitError as exc:
            raise OcrProviderError("판독 요청이 사용량 한도에 걸렸습니다. 잠시 후 재시도하십시오.") from exc
        except anthropic.APIStatusError as exc:
            raise OcrProviderError(f"판독 API 오류({exc.status_code}): {exc.message}") from exc
        except anthropic.APIConnectionError as exc:
            raise OcrProviderError(
                "판독 API에 연결할 수 없습니다. 오프라인이면 manual 엔진으로 직접 입력하십시오."
            ) from exc

        if response.stop_reason == "refusal":
            raise OcrProviderError("판독 요청이 거부되었습니다. 캡처에 민감정보가 포함됐는지 확인하십시오.")
        for block in response.content:
            if getattr(block, "type", None) == "tool_use":
                payload = OcrPayload.model_validate(block.input)
                return _mask(payload) if config.OCR_MASK_SENSITIVE else payload
        raise OcrProviderError("판독기가 report_screen 도구를 호출하지 않았습니다.")


_WBS_TAIL = re.compile(r"(?<=-)\d+(?=-|$)")


def _mask(payload: OcrPayload) -> OcrPayload:
    """WBS Code 후미·화면 제목의 고객사명 추정 부분을 가린다(§8.2)."""
    for row in payload.rows:
        if row.wbs_code and row.wbs_code.value:
            row.wbs_code.value = _WBS_TAIL.sub("****", row.wbs_code.value, count=1)
    return payload


_REGISTRY: dict[str, type] = {
    "manual": ManualProvider,
    "fixture": FixtureProvider,
    "claude": ClaudeVisionProvider,
}


def get_provider(name: str | None = None) -> OcrProvider:
    key = (name or config.OCR_PROVIDER).lower()
    cls = _REGISTRY.get(key)
    if cls is None:
        raise ValueError(f"알 수 없는 판독 엔진: {name!r} (사용 가능: {sorted(_REGISTRY)})")
    return cls()
