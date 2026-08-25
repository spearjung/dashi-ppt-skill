---
name: james-report-ppt
description: |
  James(정창모, 딜로이트 컨설팅 AI그룹 리더)의 `james-report` 산출물 표준을 dashi-ppt
  덱 생성기에 연결하는 브릿지 스킬. `dashi-ppt` 스킬로 PPT·HTML 덱을 만들 때 반드시 함께
  로드하여 ZERO META/ZERO OBVIOUS, 개조식 국문, 액션 타이틀(Minto), 마인드맵 개요,
  딜로이트 그린(#006940) 팔레트를 goal.json 단계에서 강제할 것.
  트리거: "딜로이트 스타일 PPT", "컨설팅 덱", "임원 보고 장표", "제안서 덱", "장표 만들어줘",
  "james 스타일로 PPT", "dashi로 컨설팅 자료" — 또는 클라이언트(E1, 원익, 삼성, 현대모비스,
  SK하이닉스, 신한은행, 대한항공, 동양·ABL생명, KB, 팀스파르타 등) 대상 덱 요청 시 즉시 적용.
---

# James Report × Dashi PPT 브릿지

`james-report`의 산출물 표준을 `dashi-ppt` 생성 파이프라인(goal.json → 렌더)에 강제 적용함.

## 규칙 우선순위 (충돌 시)

1. `james-report` 원칙 0~5 (ZERO META, 마인드맵, Minto, 개조식, 딜로이트 그린, 도식 품질)
2. 본 스킬 (dashi-ppt 필드·워크플로우로의 번역 규칙)
3. `dashi-ppt` SKILL.md (생성기 조작 규칙)

`dashi-ppt`의 "비문안 props 변경 금지" 규칙에 대한 **유일한 예외는 액센트 색상 prop**(`accentColor` / `accent`)임 — 딜로이트 그린 적용을 위해 본 스킬이 명시 허용함. 그 외 레이아웃·컴포넌트·CSS·메타데이터는 여전히 손대지 않음.

## 선행 로드

| 상황 | 함께 읽을 것 |
|---|---|
| 항상 | `james-report` 스킬 SKILL.md (상위 규칙) |
| 항상 | `dashi-ppt` 스킬 SKILL.md (생성기 조작) |
| 테마 선택 | `references/deloitte-theme.md` |
| 문안 작성·검수 | `references/zero-meta-checklist.md` |
| 단계별 실행 | `references/workflow.md` |

## 딜로이트 그린 테마 프리셋

dashi-ppt는 페이지 컴포넌트가 사전 빌드된 12개 테마 팩으로 고정되어 있고, 배포판에 페이지 소스와 `metadata:update` 체인이 없어 **13번째 네이티브 테마 팩은 이 저장소에서 생성 불가함.** 대신 액센트 컨트롤을 노출하는 테마 팩 위에 딜로이트 팔레트를 얹는 **프리셋**으로 제공함.

| 프리셋 | 베이스 | 용도 | 액센트 prop |
|---|---|---|---|
| `deloitte-white` (기본) | `theme07` 冷白调研风 | 임원 보고, 제안서, ISP, 백서 | `accentColor` (71/71 페이지) |
| `deloitte-chart` | `theme05` 色谱图表风 | 데이터·성과 분석, KPI 덱 | `accentColor` (92/94 페이지) |
| `deloitte-dark` | `theme06` 深色图谱风 | 전략 발표, 아키텍처·토폴로지 | `accent` (83/83 페이지) |
| `deloitte-light` | `theme01` 轻拟态风 | 강의 자료, 밝은 톤 요청 | `accentColor` (66/84 페이지) |

정의 원본: `themes/deloitte-green.json`. 프리셋 미지정 시 `deloitte-white`.

액센트 스탬핑은 손으로 하지 않고 스크립트로 처리함:

```bash
node <skill-root>/scripts/apply-deloitte-theme.mjs --goal <deck>/goal.json --preset deloitte-white --write
```

액센트 컨트롤이 없는 레이아웃은 스크립트가 경고로 보고함 — 해당 페이지는 액센트 컨트롤이 있는 레이아웃으로 교체함.

## 문안 강제 규칙 (goal.json 필드 매핑)

`james-report` 원칙 0·1·2·3을 dashi-ppt 필드로 번역함.

- **커버 서브타이틀** (`presentation.summary`, 커버 페이지) — 내용 요약 금지, so-what 주장만. `goal` 필드의 문장을 그대로 복사하지 않음
- **모든 페이지 제목** (`presentation.title` / `titleShort`) — 명사구 금지, 결론 문장(액션 타이틀). "~을 제안함/제시함" 류 보고 행위 서술 금지
- **`presentation.takeaway`** — 페이지당 핵심 메시지 1개, `james-report`의 MESSAGE 레이블 역할
- **`presentation.items[].label/detail`, `summary`, 모든 문안 필드** — 개조식 종결(~임/~함/~됨) 통일. 평서형("~한다")·경어체("~합니다") 금지
- **`meta.brand` / `meta.pageLabel` / 푸터 계열** — 출처·버전·범위 메타 라인 금지("기준 문서", "범위 ·", "본 자료는"). 페이지 코드는 P-prefix
- **장식 기호 금지** — 문안 필드의 `×`, `!`, `⚠`, `→` 제거(수식 용례는 보존)
- **items 개수** — MECE 3~5개 그룹 유지. `fillPlan.arrays[].visibleCount`가 6 이상을 요구하면 그 레이아웃을 후보에서 제외

검수는 린터로 강제함:

```bash
node <skill-root>/scripts/lint-zero-meta.mjs <deck>/goal.json
```

위반 0건이 아니면 렌더하지 않음.

## 마인드맵 개요 (원칙 1)

`james-report` 원칙 1은 예외가 없음 — 덱에도 **커버 직후 2페이지에 전체 조망 페이지**를 배치함.

- dashi-ppt 레이아웃 중 `matrix` / `process` / `timeline` 구조 가족에서 분기 표현이 가능한 페이지를 선택하고, `presentation.items`에 중심 명제 → 브랜치(전선/실행축) → 리프 구조를 담음
- 브랜치는 목차 나열이 아니라 실행 논리의 수렴 구조로 설계함
- 조망 페이지 리드문도 ZERO META — "본 덱은 ~을 다룸" 류 금지, 전략 구조 자체만 진술함

## 도식 (원칙 5)

- dashi-ppt 페이지 컴포넌트가 제공하는 차트·프로세스·매트릭스 레시피를 우선 사용함. 텍스트 카드 나열로 관계·프로세스를 표현하지 않음
- 컴포넌트 레시피로 표현 불가능한 개념 모델(Chevron, 2x2, 사이클/PDCA, 피라미드, 허니콤, 5-Gate, 스윔레인)은 `james-report`의 `references/diagram-quality.md` 규칙대로 SVG로 만들고 PNG로 변환하여 미디어 슬롯에 넣음 — `media:stage`로 스테이징 후 상대 경로 참조
- 삽입한 도식은 2단 검증 의무 그대로 적용함 — 좌표 린터 + 실렌더 확인

## 워크플로우

1. **요구 파악** — 대상 독자, 최종 형식(HTML/PPTX), 폐쇄망 여부, 클라이언트 브랜드. 브랜드 미지정 시 딜로이트 그린
2. **프리셋 선택** — 위 표에서 결정. 사용자가 dashi-ppt 스타일 그리드에서 직접 고르길 원하면 그 선택을 존중하되, 액센트 컨트롤 없는 테마면 딜로이트 팔레트 미적용을 사전 고지함
3. **구조 설계** — Minto 트리 → 마인드맵 조망 페이지 초안 → 페이지별 액션 타이틀 확정
4. **문안 작성** — 페이지별 `content.presentation` 문안 팩을 개조식·ZERO META로 일괄 작성
5. **scaffold·렌더** — `dashi-ppt` 워크플로우 그대로 진행
6. **액센트 스탬핑** — `apply-deloitte-theme.mjs --write`
7. **검증** — `lint-zero-meta.mjs` → `validate:goal-spec` → `validate:goal-copy` 순, 전부 통과 후 렌더
8. **QA** — 아래 체크리스트 전 항목

## 제출 전 QA 체크리스트

1. ☐ `lint-zero-meta.mjs` 위반 0건
2. ☐ 커버 `presentation.summary`가 so-what 주장인가 (`goal` 필드 복사면 실패)
3. ☐ 마인드맵 조망 페이지가 커버 직후에 있는가
4. ☐ 모든 페이지 `title`이 액션 타이틀인가 — 명사형·행위 서술 0건
5. ☐ 개조식 종결 통일 — 평서형·경어체 잔여 0건
6. ☐ 장식 기호 잔여 0건
7. ☐ `apply-deloitte-theme.mjs` 경고 0건 (액센트 미지원 레이아웃 잔존 없음)
8. ☐ 삽입 도식: 텍스트 겹침·경계 이탈 0건, 좌표 린터 + 실렌더 통과
9. ☐ 수치·ROI 검산 완료, 사실 주장에 실존 확인된 출처
10. ☐ `validate:goal-spec` + `validate:goal-copy` 통과, 템플릿 기본 문안(AI Capital / Key Metrics / End of Report 등) 잔여 0건
