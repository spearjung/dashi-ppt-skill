# ZERO META 체크리스트 — dashi-ppt goal.json 필드 기준

`james-report` 원칙 0(ZERO META/ZERO OBVIOUS)·2(액션 타이틀)·3(개조식)을 goal.json 의 실제 필드로 번역함. 전문은 james-report 스킬의 `references/zero-meta.md`·`references/korean-style.md` 참조.

## 필드별 강제 규칙

| goal.json 경로 | 규칙 | 위반 예 |
|---|---|---|
| `title` (덱 최상위) | 결론 문장 또는 주제 명제. 파일명·버전 표기 금지 | "AX 추진 전략 보고서 v0.5" |
| `goal` | 내부 지시문 — 슬라이드 문안으로 복사 금지 | 커버 `summary` 에 그대로 복사 |
| `slides[0].content.presentation.summary` | 커버 서브타이틀 — so-what 주장. 내용 요약·범위 서술 금지 | "~을 분석·설계·구축하는 표준 절차" |
| `...presentation.title` / `titleShort` | 액션 타이틀(결론 문장). 명사구·보고 행위 서술 금지 | "AI 도입 방안", "~을 제안함" |
| `...presentation.takeaway` | 페이지당 핵심 메시지 1개 | 요약 재진술 |
| `...presentation.summary` (본문) | 개조식, 한 논점 | "~합니다", "~한다" |
| `...presentation.items[].label` | 개조식 짧은 명제. MECE 3~5개 | 6개 이상 파편 나열 |
| `...presentation.items[].detail` | 정량 근거 포함. 자명한 사실 재진술 금지 | "3개 주체가 겹치지 않게 역할을 나눔" |
| `...content.meta.brand` / `pageLabel` | 출처·버전·범위 메타 라인 금지. 페이지 코드는 P-prefix | "기준 문서 · v0.5", "S1 / 12" |
| 모든 문안 필드 | 장식 기호(`×` `!` `⚠` `→`) 금지 — 수식 용례는 보존 | "속도 → 품질" |
| 모든 문안 필드 | 템플릿 기본 문안 잔여 0건 | "Key Metrics", "感谢阅读" |

## 금지 문자열 (린터 검출 대상 — error)

```
기준 문서 / 범위 · / 본 자료는 / 본 보고서 / 이 보고서는 / 본 덱은
클릭 시 / 읽는 법 / 한눈에 / 이후 다룸 / 아래 그림 참조
~을 다룬다 / ~에서 다룸 / ~을 제안함 / ~을 제시함 / ~을 정리한 자료
작업 보드 / ~축은 / ~의 실체
```

## 개조식 종결 (린터 검출 대상 — error)

- 허용: `~임` `~함` `~됨` `~음` (명사형 종결)
- 금지(경어체): `~합니다` `~습니다` `~입니다` `~하세요` `~십시오` `~어요` `~예요`
- 금지(평서형): `~한다` `~된다` `~이다` `~있다` `~없다` `~만든다` `~본다`
- 예외: 제안서에 그대로 실릴 인용 문안(킬 라인·슬로건·Executive Summary 확정 문안)은 경어체 유지 — 이 경우 린터를 `--warn-only` 로 돌리고 해당 항목만 수동 승인함

## 자명(自明) 표현 (기계 검출 불가 — 수동 검수)

클라이언트가 이미 아는 것을 인사이트인 척 쓰지 않음.

- ❌ 클라이언트의 기존 계획 재진술
- ❌ 정의상 참인 문장("역할을 겹치지 않게 나눔")
- ✅ 클라이언트가 몰랐던 것, 판단에 실제로 영향을 주는 것

## 실행

```bash
node <skill-root>/scripts/lint-zero-meta.mjs <deck>/goal.json          # error 있으면 종료 코드 1
node <skill-root>/scripts/lint-zero-meta.mjs <deck>/goal.json --json   # 프로그램 파싱용
node <skill-root>/scripts/lint-zero-meta.mjs <deck>/goal.json --warn-only
```

린터는 다음 필드를 검사에서 제외함 — `contentMap`, `controls`, `media`, `mediaSlots`, `preview`, `grid`, `designIntent` 하위 전체, 그리고 `id/key/type/kind/color/accent/layout/href/src` 등 비문안 키.

warn 항목(장식 기호, 한자 전용 문안, 명사구 제목)은 오탐 가능성이 있으므로 판단 후 처리하되, **제출 전에는 warn 도 0건이어야 함** — 정당한 사유가 있는 항목은 사유를 남김.
