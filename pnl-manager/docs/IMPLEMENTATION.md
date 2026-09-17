# 구현 대응표 — PRD 요구사항 ↔ 코드

PRD의 각 요구사항이 어디에 구현되고 무엇으로 검증되는지 정리한다.

## 기능 요구사항

| 요구 | 구현 | 검증 |
|---|---|---|
| FR-01 프로젝트 마스터 | `api/engagements.py`, `models/__init__.py` (Engagement·Contract·Wbs) | `test_verification_flow.py::test_contract_period_overlap_rejected` |
| FR-02 캡처 업로드 | `services/uploads.py`, `ocr/classifier.py`, `pages/UploadPage.tsx` | `test_e2e_kor01434.py::test_step1_*`, `::test_step7_*` |
| FR-03 OCR·표 구조 인식 | `ocr/schema.py`, `ocr/units.py`, `ocr/pipeline.py`, `ocr/providers.py` | `test_units_and_confidence.py`, `test_verification_flow.py::test_rows_split_*` |
| FR-04 필드별 신뢰도 | `ocr/confidence.py` | `test_units_and_confidence.py` (등급 4종·고영향 필드) |
| FR-05 검증·확정 화면 | `services/verification.py`, `api/verify.py`, `pages/VerifyPage.tsx`, `components/EditableTable.tsx` | `test_verification_flow.py::test_six_actions_supported` 외 |
| FR-06 산술 교차검증 | `rules/arithmetic.py` | `test_arithmetic.py` (10건) |
| FR-07 중복 판정 | `rules/duplicates.py` | `test_duplicates.py` (Key 8종 + 5개 상황) |
| FR-08 Snapshot 관리 | `services/snapshots.py`, `components/SnapshotDiff.tsx` | `test_verification_flow.py::test_snapshot_*`, `test_e2e_kor01434.py::test_step6_*` |
| FR-09 이상징후 탐지 | `rules/anomalies.py`, `services/issues.py`, `components/IssuePanel.tsx` | `test_anomalies.py`, `test_issue_actions.py` |
| FR-10 손익 계산 | `calc/formulas.py`, `services/pnl.py` | `test_formulas.py` (26건) |
| FR-11 시나리오 계산기 | `calc/scenario.py`, `pages/ScenarioPage.tsx` | `test_formulas.py::test_scenario_*` |
| FR-12 대시보드·조치사항 | `services/dashboard.py`, `services/issues.py::refresh_action_items`, `pages/DashboardPage.tsx` | `test_e2e_kor01434.py::test_action_items_registered` |

## 웹 배포 (PRD 범위 확장)

PRD는 로컬 실행을 전제했으나 웹 서비스로 운영하기로 정해 다음을 추가했다.

| 항목 | 구현 | 검증 |
|---|---|---|
| 공용 비밀번호 인증 | `auth.py`(HMAC 서명 세션·시도 제한), `api/auth.py`, `pages/LoginPage.tsx` | `test_auth.py` (13건), `frontend/tests/auth-smoke.mjs` (9건) |
| 단일 오리진 SPA 서빙 | `main.py` — `PNL_STATIC_DIR` 존재 시 정적 자원과 SPA 폴백 제공 | `auth-smoke.mjs`, 경로 이탈 차단 테스트 |
| 보안 헤더·API 명세 보호 | `main.py::security_and_auth` — CSP·XFO·nosniff, 인증 시 `/docs` 차단 | `test_auth.py::test_api_docs_are_protected` |
| 업로드 검증 | `services/uploads.py` — 크기 상한과 magic byte 확인 | `test_verification_flow.py`, `test_auth.py` |
| 컨테이너·호스팅 | `Dockerfile`(멀티스테이지), `docker-compose.yml`, `fly.toml`, `render.yaml` | 런타임 구성은 실제 실행으로 확인, 이미지 빌드는 미검증(§미구현 범위) |
| PostgreSQL | `PNL_DATABASE_URL` + `requirements-postgres.txt` | SQLite에서만 실행 검증 |

## 비기능 요구사항

| 요구 | 구현 |
|---|---|
| 감사 추적 | `services/audit.py` — 모든 확정·수정·제외·재분류에 행위자·시점·전후 값 기록 |
| 재현성 | `Snapshot.result` + `formula_version`, `GET /api/engagements/{id}/pnl?snapshot_id=` |
| 정확성 | `rules/arithmetic.py` 불일치 시 Medium 강등 및 확정 보류 |
| 단위 일관성 | `ocr/units.py` 원(KRW) 정수 정규화, 표시 변환은 `lib/format.ts` |
| 가용성 | `ManualProvider` + `POST /uploads/{id}/manual-records` — 오프라인 직접 입력 |
| 처리 시간 | 판독은 업로드와 분리된 `POST /uploads/{id}/ocr` 로 수행 |

## PRD 명세를 구체화한 판단

PRD가 열어 둔 부분에 대해 구현이 택한 해석이다. 변경 시 이 문서와 테스트를 함께 고친다.

1. **WBS 단위 LTD 배분** — PRD §3.2의 LTD는 Engagement 단위 산식이지만 §12는 WBS별
   예상 LTD를 요구한다. 계약금액을 보유한 단위는 계약 차수이므로 LTD는 차수 단위로
   계산한다. 차수당 WBS 다중 구성은 예외로 확인되어 균등 분할하고 경고를 남긴다.
   정상 구성(차수당 WBS 1개)에서는 전액이 배분되어 §12 기대값과 일치한다.
   (`calc/formulas.py`)
2. **차수 간 비상계** — Engagement LTD 필요액은 차수별 초과분의 합이다. 1차가 초과하고
   2차에 잔액이 있어도 상계하지 않는다. 상계하면 초과 차수의 상각 필요액이 감춰진다.
3. **기간 오류와 귀속 오류의 구분** — 발생 기간이 WBS 유효기간 이후이고 **다음 차수 WBS가
   존재할 때만** 귀속 오류로 본다. 계약기간 자체를 벗어났거나 옮길 WBS가 없으면 기간
   오류다. 옮길 곳이 없는 건에 "재분류" 조치를 제안하지 않기 위함이다.
4. **귀속 오류는 행 단위** — 한 행의 Time·Expense·OS는 같은 발생액이므로 필드별로 쪼개지
   않고 행(동일 WBS·동일 조회 기간) 단위 Issue 하나로 묶는다. §12.2가 "행"을 단위로
   기술하고 제안 조치도 행 전체에 적용된다.
5. **중복은 확정 단계에서만 제거** — 계산 계층은 같은 기간의 확정 레코드를 모두 합산한다.
   중복은 FR-07 판정으로 확정 단계에서 제외·대체되므로, 계산 계층이 기간 기준으로 다시
   덮어쓰면 재분류로 한 WBS에 모인 동일 기간 값이 사라진다(§12.2-4).
6. **LTD 필요액과 기 조정액 분리** — `ltd_required`는 max(0, EAC − 계약금액), `ltd_adjusted`는
   기록된 LTD 조정액 합, `ltd_outstanding`은 그 차이다. §12가 말하는 "예상 LTD"는
   `ltd_required`다.
7. **Backlog 미입력** — 잔여 투입 예상액을 0으로 계산하되 `backlog_entered=false`와
   `provisional=true`를 함께 반환해 화면에서 "미입력/잠정치"로 표시한다(FR-10).
8. **종료일 연장 가정** — 시나리오의 종료일 연장은 현재 월별 투입 수준이 유지된다고 보아
   `연장 개월 × (잔여 MM ÷ 계획 개월 수)` 만큼 잔여 MM을 늘린다.
9. **조치사항 선택은 의사결정 기록** — LTD·Billing 조치는 값을 바꾸지 않고 선택과 시점만
   기록한다. 조건이 남아 있어도 재오픈하지 않으며(선택 기록 보존), 조건 자체는 대시보드의
   "조치 필요 프로젝트"가 계속 노출한다.
10. **WBS Code 접두사 매칭** — 화면 코드가 마스터보다 하위 레벨까지 표기되므로
    (마스터 `KOR01434-01-01` / 화면 `KOR01434-01-01-01-1000`) 정확 일치 → 마스터가 화면
    코드의 접두사 → 화면 코드가 마스터의 접두사 순으로 찾는다.
11. **Billing 항목 유형 확장** — Billing 금액이 화면 캡처로 들어오므로 PRD §6.2의
    item_type 열거값에 `billing_planned`(청구 예정액)·`billing_unbilled`(미청구액)·
    `billable_expense`(청구가능 경비)를 더했다. `billing`은 청구 완료액으로 좁혀
    BILLING_PLAN의 네 속성과 1:1 대응한다. 청구 예정액·미청구액은 손익 판단에 직접
    쓰이므로 고영향 필드로 다룬다.
12. **Billing 값의 단일 출처** — Billing 화면에서 만들어진 계획(BillingPlan)이 있으면
    그 값만 쓰고, 없을 때만 WIP 등 다른 화면의 `billing` 항목을 쓴다. 두 경로를 함께
    더하면 같은 청구액이 중복 집계된다. 미청구액은 화면 표시값을 우선하고, 없을 때만
    누적 사용액 − 청구액으로 계산한다.
13. **조치사항의 조건 해소 처리** — 조건이 사라진 조치사항은 자동으로 닫고
    `selected_action=condition_cleared`로 기록한다. 열어 둔 채 수치만 갱신하면 이미
    해결된 항목이 낡은 금액으로 계속 남는다. 반대로 EP가 조치를 선택한 건은 조건이
    남아 있어도 재오픈하지 않는다(의사결정 기록 보존).
14. **행위자 기록의 출처** — 인증이 켜지면 확정·수정 기록의 행위자는 세션의 로그인
    이름이며 요청 본문 값보다 우선한다. 본문 값은 위조할 수 있다. 공용 비밀번호
    방식이므로 이름은 자기 신고값이고, 개인별 책임 추적에는 계정 전환이 필요하다.

## 미구현 범위

- **개인별 계정·권한** — 공용 비밀번호 하나로 운영하므로 비밀번호를 아는 사람은 모두 같은
  권한을 갖는다. 행위자 이름은 로그인 시 자기 신고값이다. EP·EM 역할 구분과 개인별 책임
  추적이 필요하면 사용자별 계정 또는 사내 SSO로 전환해야 한다.
- **컨테이너 이미지 빌드 검증** — Dockerfile·compose·호스팅 설정을 작성했으나 이 환경에
  Docker 데몬이 없어 이미지 빌드는 실행하지 못했다. 이미지가 하는 일(프런트엔드 빌드,
  단일 오리진 서빙, 인증, 보안 헤더, SPA 폴백)은 같은 구성으로 프로세스를 띄워 확인했다.
  첫 배포 시 빌드 로그를 확인해야 한다.
- **PostgreSQL 실행 검증** — 드라이버와 접속 문자열 경로는 마련했으나 검증은 SQLite에서만
  수행했다. 첫 배포 후 스키마 생성과 손익 계산 결과를 확인해야 한다.
- **수평 확장** — 로그인 시도 제한 카운터가 프로세스 메모리에, 캡처 원본이 인스턴스 로컬
  디스크에 있다. 인스턴스를 늘리려면 파일 저장소와 카운터를 외부로 분리해야 한다.
- **로컬 암호화 볼륨**(PRD §8.2) — OS·디스크 수준 설정이므로 애플리케이션 범위 밖이다.
  클라우드 호스팅에서는 제공자의 저장 암호화에 의존한다.
- **PaddleOCR 대체 엔진**(§8.1) — 어댑터 인터페이스(`ocr/providers.py`)만 마련했다.
  `OcrProvider` 프로토콜을 구현하고 `_REGISTRY`에 등록하면 추가된다.
