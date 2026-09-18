"""KOR01434 수용 기준 시나리오 데이터(§12).

계약 구성
  1차 계약(seq 0) 238,000,000원 / 2025-05-01 ~ 2025-10-31 / WBS KOR01434-01-01
  2차 계약(seq 1)  50,000,000원 / 2025-11-01 ~ 2025-12-31 / WBS KOR01434-01-02

캡처 A(1차 WBS, wip)
  행1 2025-05~10  Time 263,746,000 / Expense 6,216,247 / 합계 269,962,247
  행2 2025-11~12  Time   8,030,000 / Expense 1,865,867 / 합계   9,895,867  ← 계약기간 이후
캡처 B(2차 WBS, wip)
  행1 2025-11~12  Time  72,000,000 / Expense 5,629,160 / 합계  77,629,160
  행2 LTD 조정액 10,000,000 / 추가 계약금액 50,000,000

기대 LTD(§12.2)
  재분류 전  1차 41,858,114 / 2차 27,629,160
  재분류 후  1차 31,962,247 / 2차 37,525,027 (= 27,629,160 + 9,895,867)
"""

from __future__ import annotations

ENGAGEMENT_CODE = "KOR01434"

CONTRACT_1_AMOUNT = 238_000_000
CONTRACT_2_AMOUNT = 50_000_000

WBS_1 = "KOR01434-01-01"
WBS_2 = "KOR01434-01-02"

# 기대값
LTD_WBS1_AFTER = 31_962_247
LTD_WBS2_BEFORE = 27_629_160
RECLASSIFIED_AMOUNT = 9_895_867
LTD_WBS2_AFTER = 37_525_027
LTD_WBS1_BEFORE = LTD_WBS1_AFTER + RECLASSIFIED_AMOUNT  # 41,858,114

ENGAGEMENT_PAYLOAD = {
    "name": "KOR01434 손익관리 고도화",
    "client": "가상 고객사",
    "engagement_code": ENGAGEMENT_CODE,
    "contract_type": "fixed_price",
    "ep": "EP",
    "em": "EM",
    "start_date": "2025-05-01",
    "end_date": "2025-12-31",
    "currency": "KRW",
    "contracts": [
        {
            "seq": 0,
            "amount": CONTRACT_1_AMOUNT,
            "valid_from": "2025-05-01",
            "valid_to": "2025-10-31",
            "wbs_list": [{"code": WBS_1, "name": "1차 계약 WBS"}],
        },
        {
            "seq": 1,
            "amount": CONTRACT_2_AMOUNT,
            "valid_from": "2025-11-01",
            "valid_to": "2025-12-31",
            "wbs_list": [{"code": WBS_2, "name": "2차 변경계약 WBS"}],
        },
    ],
}

CAPTURE_A = {
    "screen_type": "wip",
    "screen_title": "Work In Progress (단위: 원)",
    "as_of_date": "2025-12-31",
    "unit": "KRW",
    "rows": [
        {
            "row_index": 1,
            "wbs_code": {"value": f"{WBS_1}-01-1000", "confidence": "high"},
            "period": {"from": "2025-05-01", "to": "2025-10-31"},
            "value_basis": "period",
            "fields": [
                {
                    "item_type": "time",
                    "raw_label": "Time",
                    "amount": 263_746_000,
                    "confidence": "high",
                },
                {
                    "item_type": "expense",
                    "raw_label": "Expense",
                    "amount": 6_216_247,
                    "confidence": "high",
                },
            ],
        },
        {
            "row_index": 2,
            "wbs_code": {"value": f"{WBS_1}-01-1000", "confidence": "high"},
            "period": {"from": "2025-11-01", "to": "2025-12-31"},
            "value_basis": "period",
            "fields": [
                {
                    "item_type": "time",
                    "raw_label": "Time",
                    "amount": 8_030_000,
                    "confidence": "high",
                },
                {
                    "item_type": "expense",
                    "raw_label": "Expense",
                    "amount": 1_865_867,
                    "confidence": "high",
                },
            ],
        },
    ],
    "totals": [
        {"raw_label": "Total", "amount": 269_962_247, "row_index": 1},
        {"raw_label": "Total", "amount": 9_895_867, "row_index": 2},
    ],
    "arithmetic_checks": [{"rule": "time+expense=total", "passed": True, "diff": 0}],
}

CAPTURE_B = {
    "screen_type": "wip",
    "screen_title": "Work In Progress (단위: 원)",
    "as_of_date": "2025-12-31",
    "unit": "KRW",
    "rows": [
        {
            "row_index": 1,
            "wbs_code": {"value": f"{WBS_2}-01-1000", "confidence": "high"},
            "period": {"from": "2025-11-01", "to": "2025-12-31"},
            "value_basis": "period",
            "fields": [
                {
                    "item_type": "time",
                    "raw_label": "Time",
                    "amount": 72_000_000,
                    "confidence": "high",
                },
                {
                    "item_type": "expense",
                    "raw_label": "Expense",
                    "amount": 5_629_160,
                    "confidence": "high",
                },
            ],
        },
        {
            "row_index": 2,
            "wbs_code": {"value": f"{WBS_2}-01-1000", "confidence": "high"},
            "period": {"from": "2025-11-01", "to": "2025-12-31"},
            "value_basis": "period",
            "fields": [
                {
                    "item_type": "ltd",
                    "raw_label": "LTD Adjustment",
                    "amount": 10_000_000,
                    "confidence": "high",
                },
                {
                    "item_type": "contract_amount",
                    "raw_label": "Change Order Amount",
                    "amount": CONTRACT_2_AMOUNT,
                    "confidence": "high",
                },
            ],
        },
    ],
    "totals": [{"raw_label": "Total", "amount": 77_629_160, "row_index": 1}],
}
