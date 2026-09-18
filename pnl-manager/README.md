# 프로젝트 손익관리 프로그램

캡처 몇 장으로 담당 프로젝트 전체의 손익과 필요 조치를 즉시 확인한다.
**OCR은 임시값, 확정은 사람, 저장은 Snapshot.**

사내 손익 시스템(Interlock, SWIFT WIP, Billing, Backlog, Expense·OS)의 화면 캡처를
업로드하면 판독·검증을 거쳐 확정된 값만으로 종료예상 손익과 LTD 필요액을 산출한다.
설계 근거는 [`docs/PRD.md`](docs/PRD.md)이며, 아래 문서는 실행 방법을 다룬다.

---

## 1. 웹으로 배포하기

프런트엔드를 빌드해 백엔드가 같은 오리진에서 서빙하므로 **포트가 하나**다.
관리형 호스팅에 컨테이너 하나만 올리면 된다.

### 1.1 배포 전 준비

| 준비물 | 설명 |
|---|---|
| 공용 비밀번호 | 12자 이상. 짧으면 기동을 거부한다 |
| `ANTHROPIC_API_KEY` | 판독 엔진용. 없으면 자동 판독만 실패하고 직접 입력은 가능 |
| 영속 볼륨 | **필수.** 캡처 원본이 파일로 저장되므로 볼륨 없이 재배포하면 이미지가 사라진다 |
| PostgreSQL | 권장. 관리형 DB를 만들고 `PNL_DATABASE_URL`로 연결한다 |

### 1.2 Fly.io

```bash
fly launch --no-deploy                       # 앱 생성 (fly.toml의 app 이름을 맞춘다)
fly volumes create pnl_data --size 3 --region nrt
fly postgres create --name pnl-db --region nrt
fly postgres attach pnl-db                   # DATABASE_URL 주입

fly secrets set \
  PNL_APP_PASSWORD='충분히-긴-공용-비밀번호' \
  PNL_SECRET_KEY="$(openssl rand -hex 32)" \
  ANTHROPIC_API_KEY='sk-ant-...' \
  PNL_DATABASE_URL='postgresql+psycopg://...'   # fly postgres attach가 준 값을 psycopg 형식으로

fly deploy
fly open                                     # 로그인 화면이 뜬다
```

> `fly postgres attach`는 `postgres://` 형식을 주므로 `postgresql+psycopg://` 로 바꿔
> `PNL_DATABASE_URL`에 넣는다. 그대로 쓰면 드라이버를 찾지 못한다.

### 1.3 Render

`render.yaml`이 웹 서비스·디스크·PostgreSQL을 함께 정의한다. 저장소를 연결하면
Blueprint로 인식한다. `PNL_APP_PASSWORD`와 `ANTHROPIC_API_KEY`만 대시보드에서 입력한다.

### 1.4 Docker Compose (사내 서버·로컬 확인)

```bash
cp .env.example .env        # PNL_APP_PASSWORD 등을 채운다
docker compose up -d --build
# http://localhost:8000
```

### 1.5 배포 후 확인

```bash
curl -s https://<도메인>/api/health
# {"status":"ok", ..., "auth_required":true}
```

`auth_required`가 `false`면 인증이 꺼진 상태로 공개돼 있다는 뜻이다. 즉시
`PNL_APP_PASSWORD`를 설정하고 재배포한다.

첫 로그인 후 **프로젝트 마스터**에서 Engagement·계약 차수·WBS Code를 등록하면 된다.

### 1.6 운영 시 유의

- **HTTPS 필수** — `PNL_SECURE_COOKIES=1`(컨테이너 기본값)이면 세션 쿠키가 HTTPS에서만
  전송된다. 평문 HTTP로 접근하면 로그인이 되지 않는다.
- **공용 비밀번호의 한계** — 비밀번호를 아는 사람은 모두 같은 권한을 갖는다. 행위자는
  로그인 시 입력한 이름으로 기록되므로 자기 신고값이다. 개인별 책임 추적이 필요하면
  사용자별 계정으로 전환해야 한다(§8).
- **비밀번호 교체** — `PNL_SECRET_KEY`를 따로 두지 않으면 세션 키가 비밀번호에서
  파생되므로, 비밀번호를 바꾸면 기존 세션이 모두 무효화된다(의도된 동작).
- **단일 인스턴스** — 로그인 시도 제한과 업로드 파일이 인스턴스 로컬에 있으므로
  인스턴스를 늘리지 않는다. 늘려야 하면 파일 저장소와 제한 카운터를 외부로 빼야 한다.

---

## 2. 로컬 개발

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

## 3. 사용 흐름

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

## 4. 판독 엔진 선택

`PNL_OCR_PROVIDER` 환경변수로 전환한다. **기본값은 `claude`다.**

| 값 | 동작 | 용도 |
|---|---|---|
| `claude` | Claude Vision + JSON 스키마 강제 출력 | 기본값. 판독 정확도 우선 |
| `manual` | 판독하지 않고 직접 입력 대기 상태로 둔다 | 외부 전송 불가 환경 |
| `fixture` | 이미지 옆의 `<파일명>.ocr.json` 을 판독 결과로 사용 | 테스트·수기 판독 결과 주입 |

```bash
export ANTHROPIC_API_KEY=...        # 또는 `ant auth login`
export PNL_OCR_MASK=1               # WBS Code 후미 마스킹(선택)
```

캡처 이미지는 판독을 위해 Claude API로 전송된다. 자격증명이 없으면 자동 판독만
실패하고, 검증 화면의 직접 입력으로 계속 진행할 수 있다(오프라인 가용성, PRD §9).

`POST /api/uploads/{id}/ocr-payload` 로 판독 결과 JSON을 직접 주입하는 경로도
열려 있어, 다른 판독 도구의 결과를 넣거나 재판독 없이 값을 교체할 수 있다.

### 환경변수

| 변수 | 기본값 | 설명 |
|---|---|---|
| `PNL_APP_PASSWORD` | 없음 | **공용 비밀번호(12자 이상).** 설정하면 인증이 켜진다 |
| `PNL_AUTH_ENABLED` | 비밀번호 유무 | 인증 강제 on/off |
| `PNL_SECRET_KEY` | 비밀번호에서 파생 | 세션 쿠키 서명 키 |
| `PNL_SECURE_COOKIES` | `0` (컨테이너 `1`) | HTTPS 전용 쿠키 |
| `PNL_SESSION_HOURS` | `12` | 세션 유효 시간 |
| `PNL_LOGIN_MAX_ATTEMPTS` | `10` | IP별 로그인 실패 허용 횟수 |
| `PNL_STATIC_DIR` | `frontend/dist` | SPA 빌드 경로. 있으면 같은 오리진에서 서빙 |
| `PNL_DATA_DIR` | `../data` | 업로드 이미지·DB 저장 경로 |
| `PNL_DATABASE_URL` | SQLite URL | 예: `postgresql+psycopg://user:pw@host/pnl` |
| `PNL_OCR_PROVIDER` | `claude` | 판독 엔진 |
| `PNL_OCR_MODEL` | `claude-opus-5` | 판독 모델 |
| `PNL_OCR_MASK` | `0` | WBS Code 마스킹 |
| `PNL_MAX_UPLOAD_BYTES` | `15728640` | 업로드 1건 최대 크기(15MB) |
| `PNL_UNBILLED_THRESHOLD` | `50000000` | 미청구액 조치사항 기준치 |
| `PNL_CORS_ORIGINS` | `localhost:5173` | 허용 Origin. 단일 오리진 배포에서는 비운다 |

---

## 5. Phase 0 CLI

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

## 6. 테스트

```bash
cd backend && pytest                    # 141건 — 산식·중복·이상징후·검증·인증·Billing·CLI·E2E
cd frontend && npm run typecheck        # 타입 검사
cd frontend && npm run test:ui          # UI 스모크 24건 (개발 서버 2개 + 데모 데이터)
cd frontend && npm run test:auth        # 배포 형태 스모크 9건 (단일 오리진 + 인증)
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

배포 형태(단일 오리진 + 인증) 스모크 테스트:

```bash
cd frontend && npm run build
cd ../backend && PNL_DATA_DIR=/tmp/pnl-web python scripts/seed_demo.py --reset
PNL_DATA_DIR=/tmp/pnl-web PNL_STATIC_DIR=../frontend/dist \
  PNL_APP_PASSWORD=demo-password-1234 PNL_SECURE_COOKIES=0 PNL_CORS_ORIGINS="" \
  uvicorn app.main:app --port 8100 &
cd ../frontend && npm run test:auth
```

---

## 7. 구조

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
├── docs/                # PRD, 구현 대응표, 데모용 판독 결과 JSON
├── Dockerfile           # 프런트엔드 빌드 + 백엔드 단일 이미지
├── docker-compose.yml   # 앱 + PostgreSQL
├── fly.toml             # Fly.io 배포 설정
├── render.yaml          # Render 배포 설정
└── .env.example         # 환경변수 예시
```

---

## 8. 설계 원칙

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

## 9. 남은 결정 사항

| 항목 | 현재 | 전환 방법 |
|---|---|---|
| 인증 | 공용 비밀번호 + 자기 신고 이름 | 개인별 책임 추적이 필요하면 사용자별 계정 또는 사내 SSO로 전환 |
| WIP 정의 | 산식 계산값 우선, 화면값과 차이를 경고 | `wip` 항목을 확정하면 화면값도 함께 보존됨 |
| 적용 Rate | Backlog 화면 Rate | 시나리오의 `적용 Rate` 변수로 대체 계산 |
| LTD 정의 | 계약금액 초과분(차수별) | `app/calc/formulas.py`의 산식 버전 관리로 교체 |
| 통화 | KRW 단일 | `Engagement.currency` 보유. 다중 통화는 환산 정책 필요 |
| 미청구액 기준치 | 5,000만원 | `PNL_UNBILLED_THRESHOLD` 로 조정 |
| 수평 확장 | 단일 인스턴스 | 파일 저장소(S3 등)와 로그인 제한 카운터를 외부로 분리해야 함 |

확정된 사항은 다음과 같다.

- **캡처 이미지 외부 전송** 허용 — 판독 엔진 기본값이 `claude`다.
- **차수당 WBS 다중 구성**은 예외로 간주 — 해당 구성에서는 계약금액을 균등 분할하고
  경고를 남긴다. 실제로 필요해지면 배분 기준을 정의한다.
- **Billing 금액은 화면 캡처로 입력** — 청구 예정액·완료액·미청구액·청구가능 경비를
  각각 판독해 보존한다.
