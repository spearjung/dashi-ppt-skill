# 결합 워크플로우 — james-report × dashi-ppt

`dashi-ppt` SKILL.md 의 워크플로우를 기준으로, James 표준을 강제하는 단계를 삽입함. 아래 번호는 dashi-ppt 워크플로우 단계에 대응함.

## 0. 선행 확인 (dashi-ppt 워크플로우 진입 전)

- 대상 독자 — C-level / PMO / 평가위원 / 실무 중 무엇인가
- 최종 형식 — HTML 기본. `PPTX`·`PowerPoint`·`PPT 파일` 이 명시된 경우만 PPTX
- 폐쇄망 여부 — 폐쇄망이면 외부 CDN·원격 리소스 0건
- 클라이언트 브랜드 — 미지정 시 딜로이트 그린

## 1. 목표 추출 + 프리셋 결정

dashi-ppt 는 스타일 그리드 이미지를 보여주고 테마를 묻도록 요구함. James 산출물에서는 `references/deloitte-theme.md` 의 4개 프리셋으로 후보를 좁혀 제시함 — 액센트 컨트롤이 없는 테마는 딜로이트 팔레트 적용이 불가능하므로 후보에서 제외함.

사용자가 제외된 테마를 명시적으로 고르면 그 선택을 존중하되, **딜로이트 그린 미적용을 사전에 고지함.**

`goal.themePack` 에 프리셋의 `basePack` 을 씀.

## 2. 구조 설계 (Minto)

scaffold 호출 전에 완료함.

1. 최상위 메시지 1개 확정 → 이것이 커버 `presentation.summary` 의 so-what 주장이 됨
2. 근거 그룹 3~5개(MECE) → 각 그룹이 섹션이 됨
3. 그룹별 페이지 → 각 페이지 `presentation.title` 은 결론 문장(액션 타이틀)
4. 페이지별 `takeaway` 1개 확정

## 3. 마인드맵 조망 페이지 (원칙 1, 예외 없음)

커버 직후 2페이지에 배치함.

- `layout:query` 로 `matrix` / `process` / `timeline` 구조 가족에서 분기 표현이 가능한 후보를 조회함
- `presentation.items` 에 중심 명제 → 브랜치(전선/실행축) → 리프 구조를 담음
- 컴포넌트 레시피로 수렴 구조 표현이 부족하면 SVG 마인드맵을 만들어 PNG 로 변환 후 미디어 슬롯에 넣음 (`media:stage` 로 스테이징)
- 조망 페이지 리드문도 ZERO META — 도식 배치 설명 금지, 전략 구조 자체만 진술함

## 4. 문안 팩 일괄 작성

dashi-ppt 규칙대로 페이지별 `content.presentation` 을 한 번에 씀. 여기서 `references/zero-meta-checklist.md` 의 필드별 규칙을 지킴.

- v1~v3 템플릿은 동일한 사실·수치를 공유하고 길이·정렬·시각 위계만 다르게 함 — 세 가지 이야기를 따로 만들지 않음
- v4(bespoke)는 같은 사실원에서 재구성하되 사실을 새로 만들지 않음
- 템플릿 기본 중국어 문안은 전 필드 덮어씀 — 결말 페이지 장식 문구까지

## 5. scaffold · props

```bash
npm --prefix <dashi-root>/project run goal:scaffold -- ... --out output/<deck>/goal.json
npm --prefix <dashi-root>/project run props:safe -- --goal output/<deck>/goal.json --write
```

## 6. 딜로이트 액센트 스탬핑

`props:safe` 이후, 검증 이전.

```bash
node <skill-root>/scripts/apply-deloitte-theme.mjs --goal output/<deck>/goal.json --preset deloitte-white --write
```

경고로 보고된 액센트 미지원 레이아웃은 교체하고 다시 스탬핑함.

## 7. 검증 (순서 고정)

```bash
node <skill-root>/scripts/lint-zero-meta.mjs output/<deck>/goal.json
npm --prefix <dashi-root>/project run validate:goal-spec -- output/<deck>/goal.json
npm --prefix <dashi-root>/project run validate:goal-copy -- output/<deck>/goal.json
```

`lint-zero-meta` error 가 1건이라도 있으면 렌더하지 않음.

## 8. 렌더 · 도식 2단 검증

- 렌더는 dashi-ppt 렌더 스크립트 그대로
- 삽입한 SVG 도식은 james-report 원칙 5의 2단 검증 적용 — ① 좌표 산술 린터(겹침·경계 이탈·오버플로 0건) ② Playwright/Chromium 헤드리스 스크린샷 육안 확인
- 시각 확인이 불가능한 세션이면 그 한계를 사용자에게 명시함

## 9. 산출물 인도

- HTML: 프리뷰 주소 `http://127.0.0.1:<port>/`
- PPTX: `/api/export-editable-pptx` 또는 `npm run export:pptx`. 최종적으로 PPTX 파일 경로만 전달함
- 본 스킬 SKILL.md 의 QA 체크리스트 10항목 전부 통과 후 인도함
