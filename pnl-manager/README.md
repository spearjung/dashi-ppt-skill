# 프로젝트 손익관리 프로그램

캡처 몇 장으로 담당 프로젝트 전체의 손익과 필요 조치를 즉시 확인한다.
**OCR은 임시값, 확정은 사람, 저장은 Snapshot.**

사내 손익 시스템(Interlock, SWIFT WIP, Billing, Backlog, Expense·OS)의 화면 캡처를
업로드하면 판독·검증을 거쳐 확정된 값만으로 종료예상 손익과 LTD 필요액을 산출한다.
설계 근거는 [`docs/PRD.md`](docs/PRD.md)이며, 아래 문서는 실행 방법을 다룬다.

---

## 1. 빠른 시작

### 백엔드

```bash
cd backend
pip install -r requirements-dev.txt
python scripts/seed_demo.py --reset          # 데모 데이터(선택)
uvicorn app.main:app --reload --port 8000
```

API 문서는 <http://127.0.0.1:8000/docs> 에서 확인한다.

### 프런트엔드

```bash
cd frontend
npm install
npm run dev                                   # http://127.0.0.1:5173
```

Vite 개발 서버가 `/api` 를 `http://127.0.0.1:8000` 으로 프록시한다.
다른 주소를 쓰려면 `PNL_API_URL` 을 지정한다.

---

## 2. 사용 흐름

| Step | 화면 | 하는 일 |
|---|---|---|
| 1 | 프로젝트 마스터 | Engagement·계약 차수·WBS Code 등록(최초 1회) |
| 2 | 캡처 업로드 | 여러 장 Drag & Drop, 화면 유형 선택 또는 자동 분류 위임 |
| 3 | (자동) | 표 구조 인식, 단위 정규화, 신뢰도 부여, 산술검증, 중복·이상징후 판정 |
| 4 | OCR 검증 | 값별로 확인·수정·제외·재분류·중복 표시·판독 실패 표시 후 **최종 확정** |
| 5 | 프로젝트 손익 / 시나리오 | 확정값 기준 손익·LTD·조치사항 확인, Snapshot 시점 전환 |

확정 전에는 어떤 판독값도 손익 계산에 들어가지 않는다. 고영향 필드
(계약금액·Time·Expense·Billing·LTD·날짜·금액 단위·WBS Code)는 신뢰도가 High여도
개별 확인을 거쳐야 확정 버튼이 열린다.

---

## 3. 판독 엔진 선택

`PNL_OCR_PROVIDER` 환경변수로 전환한다. **기본값은 오프라인(`manual`)이다.**

| 값 | 동작 | 용도 |
|---|---|---|
| `manual` | 판독하지 않고 직접 입력 대기 상태로 둔다 | 오프라인·정보보호 정책 미확정 시 |
| `claude` | Claude Vision + JSON 스키마 강제 출력 | 판독 정확도 우선 |
| `fixture` | 이미지 옆의 `<파일명>.ocr.json` 을 판독 결과로 사용 | 테스트·수기 판독 결과 주입 |

```bash
export PNL_OCR_PROVIDER=claude
export ANTHROPIC_API_KEY=...        # 또는 `ant auth login`
export PNL_OCR_MASK=1               # WBS Code 후미 마스킹(§8.2)
```

> **캡처 이미지는 `claude` 엔진에서 외부로 전송된다.** 사내 정보보호 정책 확인이
> 선행 결정 사항이다(PRD §10). 정책이 확정되기 전에는 `manual` 또는 `fixture` 로
> 운영하고, 판독 결과 JSON을 `POST /api/uploads/{id}/ocr-payload` 로 주입한다.

### 환경변수

| 변수 | 기본값 | 설명 |
|---|---|---|
| `PNL_DATA_DIR` | `../data` | 업로드 이미지·DB 저장 경로 |
| `PNL_DB_PATH` | `<DATA_DIR>/db.sqlite` | SQLite 파일 |
| `PNL_DATABASE_URL` | SQLite URL | PostgreSQL 전환 시 지정 |
| `PNL_OCR_PROVIDER` | `manual` | 판독 엔진 |
| `PNL_OCR_MODEL` | `claude-opus-5` | 판독 모델 |
| `PNL_OCR_MASK` | `0` | WBS Code 마스킹 |
| `PNL_UNBILLED_THRESHOLD` | `50000000` | 미청구액 조치사항 기준치 |
| `PNL_CORS_ORIGINS` | `localhost:5173` | 허용 Origin |

---

## 4. Phase 0 CLI

웹 UI 없이 캡처 → CSV 교정 → HTML 리포트까지 수행한다(PRD §11 Phase 0).

```bash
cd backend
python -m app.cli init
python -m app.cli create-project ../docs/sample-project.json
python -m app.cli ingest KOR01434 cap1.png cap2.png \
    --payload ../docs/sample-capture-wbs1.ocr.json ../docs/sample-capture-wbs2.ocr.json
python -m app.cli export-csv KOR01434 rows.csv     # action 열을 편집해 오류 교정
python -m app.cli import-csv KOR01434 rows.csv     # 확정 + Snapshot 생성
python -m app.cli report KOR01434 report.html      # 손익·LTD·시나리오 리포트
```

CSV의 `action` 열에 `confirm` / `edit` / `exclude` / `reassign` / `duplicate` 를 쓴다.
`edit` 는 `amount` 열(원 단위 정수)을, `reassign` 은 `wbs_code` 열을 함께 수정한다.

---

## 5. 테스트

```bash
cd backend && pytest                    # 119건 — 산식·중복·이상징후·검증·CLI·E2E
cd frontend && npm run typecheck        # 타입 검사
cd frontend && npm run test:ui          # UI 스모크 24건 (서버 2개 + 데모 데이터 필요)
```

`backend/tests/test_e2e_kor01434.py` 는 PRD §12 수용 기준을 그대로 검증한다.

| 검증 항목 | 기대값 |
|---|---|
| 두 캡처 자동 분류 | 각각 `wip` |
| WBS 귀속 검토 Issue | 행 단위 1건, 제안 조치 4종 |
| 재분류 전 예상 LTD | 1차 41,858,114원 / 2차 27,629,160원 |
| 재분류 후 예상 LTD | 1차 31,962,247원 / 2차 37,525,027원 |
| 검산 | 27,629,160 + 9,895,867 = 37,525,027 |
| 재분류 전·후 Snapshot | 각각 보존, 시점 재현 가능 |
| 동일 캡처 재업로드 | 해시 일치 경고, 자동 확정 안 함 |

UI 스모크 테스트 실행 절차:

```bash
cd backend && python scripts/seed_demo.py --reset
uvicorn app.main:app --port 8000 &
cd ../frontend && npm run dev &
npm run test:ui
```

---

## 6. 구조

```
pnl-manager/
├── backend/
│   ├── app/
│   │   ├── models/      # SQLAlchemy 엔티티 (PRD §6.2)
│   │   ├── ocr/         # 스키마·단위 정규화·신뢰도·분류·판독 엔진·파이프라인
│   │   ├── rules/       # 산술 교차검증·중복 판정·이상징후 탐지
│   │   ├── calc/        # 손익 산식(PRD §3.2)·시나리오
│   │   ├── services/    # 업로드·검증·Snapshot·손익·이상징후·대시보드·감사
│   │   ├── api/         # FastAPI 라우터 32개
│   │   └── cli.py       # Phase 0 CLI
│   ├── scripts/         # seed_demo.py
│   └── tests/           # KOR01434 E2E 포함 119건
├── frontend/
│   └── src/
│       ├── pages/       # Dashboard, Upload, Verify, ProjectPnl, Scenario, Master
│       ├── components/  # ImageViewer, EditableTable, SnapshotDiff, IssuePanel …
│       └── lib/         # API 클라이언트·표시 형식
├── data/                # uploads/, db.sqlite (gitignore)
└── docs/                # PRD, 데모용 프로젝트·판독 결과 JSON
```

---

## 7. 설계 원칙

- **판독값은 확정값이 아니다.** OCR 판독값(`OcrRecord`)·사용자 확인값(`ConfirmedRecord`)·
  시스템 계산값(`Snapshot`)을 3계층으로 분리하고, 손익 계산은 확정값만 입력으로 받는다.
- **최초 판독값은 불변이다.** 원본 이미지와 최초 판독 JSON을 그대로 보존하고, 수정은
  확정 계층에 원본값과 함께 기록한다.
- **단위는 원(KRW) 정수로 통일한다.** 화면 단위(원·천원·백만원)를 인식해 정규화하고,
  단위 미표시 캡처는 신뢰도 Low로 강등해 수정 또는 제외를 요구한다.
- **누적값과 기간 발생액을 섞어 더하지 않는다.** `value_basis` 로 구분 저장하고,
  한 항목에 두 기준이 함께 확정되면 누적값을 채택하고 경고한다.
- **차수 간 초과분을 상계하지 않는다.** LTD 필요액은 계약 차수별 초과분의 합이다.
- **산식 결과가 화면 표시값과 다르면 자동 확정하지 않는다.**
- **Snapshot은 덮어쓰지 않는다.** 임의 시점의 대시보드·계산 결과를 재현할 수 있다.
- **Backlog 미입력은 0이 아니다.** "미입력"으로 표시하고 종료예상값을 잠정 처리한다.

---

## 8. 미결정 사항

PRD §10의 사전 결정 사항 중 현재 구현이 택한 기본값과 전환 방법은 다음과 같다.

| 항목 | 현재 기본값 | 전환 방법 |
|---|---|---|
| OCR 엔진 | 오프라인 `manual` | `PNL_OCR_PROVIDER=claude` (정보보호 정책 확인 후) |
| WIP 정의 | 산식 계산값 우선, 화면값과 차이를 경고 | `wip` 항목을 확정하면 화면값이 함께 보존됨 |
| 적용 Rate | Backlog 화면 Rate | 시나리오의 `적용 Rate` 변수로 대체 계산 |
| LTD 정의 | 계약금액 초과분(차수별) | `app/calc/formulas.py` 의 산식 버전 관리로 교체 |
| 통화 | KRW 단일 | `Engagement.currency` 보유, 다중 통화는 환산 정책 필요 |
| 사용자 | 인증 없는 단일 사용자, 행위자명 기록 | 인증 도입 시 `confirmed_by`·`AuditLog.actor` 연결 |
| 배포 | 로컬(localhost) | PostgreSQL + 접근 통제 필요 |

로컬 실행이 전제이므로 인증·권한은 구현하지 않았다. 사내 서버 배포 시 인증 도입과
DB 전환(SQLite → PostgreSQL)이 함께 필요하다.
