"""OCR 판독·구조화 계층(§FR-03, §FR-04)."""

from .confidence import HIGH_IMPACT_FIELDS, grade_row_field, requires_individual_confirmation
from .pipeline import ingest_payload, run_ocr
from .schema import OcrPayload, OcrRow, OcrField, OCR_JSON_SCHEMA
from .units import UnitParseError, detect_unit, normalize_amount, parse_number

__all__ = [
    "HIGH_IMPACT_FIELDS",
    "OCR_JSON_SCHEMA",
    "OcrField",
    "OcrPayload",
    "OcrRow",
    "UnitParseError",
    "detect_unit",
    "grade_row_field",
    "ingest_payload",
    "normalize_amount",
    "parse_number",
    "requires_individual_confirmation",
    "run_ocr",
]
