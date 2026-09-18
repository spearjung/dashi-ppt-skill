"""OCR 출력 JSON 스키마(§6.3).

판독 결과는 자유 텍스트를 허용하지 않고 이 스키마로만 받는다(§FR-03).
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from ..enums import Confidence, ItemType, ScreenType, ValueBasis


class OcrPeriod(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_: date | None = Field(default=None, alias="from")
    to: date | None = None


class OcrValue(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    value: str | None = None
    confidence: Confidence = Confidence.MEDIUM
    bbox: list[float] | None = None


class OcrField(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    item_type: ItemType
    raw_label: str | None = None
    amount: int | float | str | None = None
    quantity: float | None = None
    unit: str | None = None
    value_basis: ValueBasis | None = None
    confidence: Confidence = Confidence.MEDIUM
    bbox: list[float] | None = None
    obstructed: bool = False
    note: str | None = None


class OcrRow(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    row_index: int = 1
    wbs_code: OcrValue | None = None
    period: OcrPeriod | None = None
    as_of_date: date | None = None
    value_basis: ValueBasis | None = None
    person_or_grade: str | None = None
    month: str | None = None
    fte_rate: float | None = None
    fields: list[OcrField] = Field(default_factory=list)


class OcrTotal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    raw_label: str | None = None
    amount: int | float | str | None = None
    row_index: int | None = None


class OcrArithmeticCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule: str
    passed: bool
    diff: float = 0.0
    row_index: int | None = None


class OcrPayload(BaseModel):
    """판독기 출력 전체. §6.3 예시와 동일한 형태를 갖는다."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    upload_id: str | None = None
    screen_type: ScreenType = ScreenType.OTHER
    screen_title: str | None = None
    as_of_date: date | None = None
    period: OcrPeriod | None = None
    unit: str | None = None
    filters: str | None = None
    rows: list[OcrRow] = Field(default_factory=list)
    totals: list[OcrTotal] = Field(default_factory=list)
    arithmetic_checks: list[OcrArithmeticCheck] = Field(default_factory=list)
    quality_warnings: list[str] = Field(default_factory=list)


#: LLM 강제 출력용 JSON Schema(tool input_schema로 전달)
OCR_JSON_SCHEMA: dict = {
    "type": "object",
    "additionalProperties": False,
    "required": ["screen_type", "rows"],
    "properties": {
        "screen_type": {"type": "string", "enum": [s.value for s in ScreenType]},
        "screen_title": {"type": ["string", "null"]},
        "as_of_date": {"type": ["string", "null"], "description": "조회 기준일 YYYY-MM-DD"},
        "period": {
            "type": ["object", "null"],
            "additionalProperties": False,
            "properties": {
                "from": {"type": ["string", "null"]},
                "to": {"type": ["string", "null"]},
            },
        },
        "unit": {
            "type": ["string", "null"],
            "description": "화면에 표시된 금액 단위. 표시가 없으면 null",
            "enum": ["KRW", "KRW_THOUSAND", "KRW_MILLION", "KRW_100M", None],
        },
        "filters": {"type": ["string", "null"]},
        "rows": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["row_index", "fields"],
                "properties": {
                    "row_index": {"type": "integer"},
                    "wbs_code": {
                        "type": ["object", "null"],
                        "additionalProperties": False,
                        "properties": {
                            "value": {"type": ["string", "null"]},
                            "confidence": {
                                "type": "string",
                                "enum": [c.value for c in Confidence],
                            },
                            "bbox": {"type": ["array", "null"], "items": {"type": "number"}},
                        },
                    },
                    "period": {
                        "type": ["object", "null"],
                        "additionalProperties": False,
                        "properties": {
                            "from": {"type": ["string", "null"]},
                            "to": {"type": ["string", "null"]},
                        },
                    },
                    "as_of_date": {"type": ["string", "null"]},
                    "value_basis": {
                        "type": ["string", "null"],
                        "enum": [v.value for v in ValueBasis] + [None],
                    },
                    "person_or_grade": {"type": ["string", "null"]},
                    "month": {"type": ["string", "null"]},
                    "fte_rate": {"type": ["number", "null"]},
                    "fields": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["item_type", "confidence"],
                            "properties": {
                                "item_type": {
                                    "type": "string",
                                    "enum": [i.value for i in ItemType],
                                },
                                "raw_label": {
                                    "type": ["string", "null"],
                                    "description": "화면의 실제 항목명을 그대로 보존",
                                },
                                "amount": {"type": ["number", "string", "null"]},
                                "quantity": {"type": ["number", "null"]},
                                "unit": {"type": ["string", "null"]},
                                "value_basis": {
                                    "type": ["string", "null"],
                                    "enum": [v.value for v in ValueBasis] + [None],
                                },
                                "confidence": {
                                    "type": "string",
                                    "enum": [c.value for c in Confidence],
                                },
                                "bbox": {"type": ["array", "null"], "items": {"type": "number"}},
                                "obstructed": {"type": "boolean"},
                                "note": {"type": ["string", "null"]},
                            },
                        },
                    },
                },
            },
        },
        "totals": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "raw_label": {"type": ["string", "null"]},
                    "amount": {"type": ["number", "string", "null"]},
                    "row_index": {"type": ["integer", "null"]},
                },
            },
        },
        "arithmetic_checks": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["rule", "passed"],
                "properties": {
                    "rule": {"type": "string"},
                    "passed": {"type": "boolean"},
                    "diff": {"type": "number"},
                    "row_index": {"type": ["integer", "null"]},
                },
            },
        },
        "quality_warnings": {
            "type": "array",
            "items": {"type": "string"},
            "description": "숫자 잘림·커서 가림·단위 미표시 등 캡처 품질 경고",
        },
    },
}
