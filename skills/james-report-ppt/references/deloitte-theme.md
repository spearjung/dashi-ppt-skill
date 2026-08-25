# 딜로이트 그린 테마 프리셋

## 왜 프리셋인가 — 네이티브 13번째 테마 팩이 불가능한 이유

dashi-ppt 배포판의 테마 팩은 다음 3종 산출물로 구성됨.

| 산출물 | 경로 | 배포판 포함 |
|---|---|---|
| 페이지 컴포넌트 소스 (`runtime.jsx`, 페이지별 JSX) | `project/src/components/themes/themeXX/` | ✗ 미포함 |
| 직렬화 메타데이터 (`metadata.js`, `generated-metadata.js`) | 동상 | ✓ 생성물만 포함 |
| 사전 빌드 런타임 (`themeXX.module.mjs`, `imported-theme-runtime.themeXX.js`) | `project/dist/theme-runtime/` | ✓ minify 산출물만 포함 |

신규 테마 팩을 만들려면 페이지 컴포넌트 소스를 작성한 뒤 `themes:import` → `metadata:update` → `build-theme-runtime` 체인을 돌려야 함. 이 체인은 `project/package.json` 의 `scripts` 에 없고, 각 테마의 `runtime.jsx` 도 배포판에서 제거되어 있음(각 테마 디렉터리에는 `metadata.js` 와 원본 디자인 소스 일부만 남아 있음). 따라서 이 저장소 안에서 `theme13` 을 만드는 것은 불가능함.

대신 페이지 컴포넌트가 이미 노출하는 **액센트 색상 컨트롤**을 딜로이트 그린으로 고정하는 프리셋으로 구현함. 액센트 컨트롤은 `type: "color"` 로 선언되어 있고 `validate-goal-spec` 이 `color` 계열 키를 비문안 필드로 처리하므로, 프리셋의 열거값(`options`)에 없는 임의 hex 도 그대로 통과함.

## 테마 팩별 액센트 컨트롤 실측

`generated-metadata.js` 기준 페이지 수 대비 액센트 컨트롤 노출 현황.

| 테마 | 이름 | 페이지 | 액센트 키 | 노출 | 기본값 |
|---|---|---|---|---|---|
| `theme01` | 轻拟态风 | 84 | `accentColor` | 66 | `#5b8def` |
| `theme02` | 炫光紫绿风 | 74 | — | 0 | — |
| `theme03` | 深浅代码风 | 77 | — | 0 | — |
| `theme04` | 玻璃糖果风 | 74 | — | 0 | — |
| `theme05` | 色谱图表风 | 94 | `accentColor` | 92 | `#E0301E` |
| `theme06` | 深色图谱风 | 83 | `accent` | 83 | `#d2fb30` |
| `theme07` | 冷白调研风 | 71 | `accentColor` | 71 | `#8FD400` |
| `theme08` | 黑金实验风 | 84 | — | 0 | — |
| `theme09` | 深蓝杂志风 | 111 | — | 0 | — |
| `theme10` | 金色指数风 | 95 | — | 0 | — |
| `theme11` | 高能增长风 | 87 | — | 0 | — |
| `theme12` | 声波霓虹风 | 86 | `accent` | 86 | `#d2fb30` |

액센트 컨트롤이 없는 6개 테마(`theme02/03/04/08/09/11`)와 `theme10`(금색 고정)은 딜로이트 팔레트 적용이 불가능하므로 James 산출물에 사용하지 않음. `theme12`(声波霓虹风)는 액센트 컨트롤은 있으나 네온 배경이 딜로이트 톤과 충돌하여 제외함.

## 프리셋

| 프리셋 | 베이스 | 액센트 | 용도 |
|---|---|---|---|
| `deloitte-white` (기본) | `theme07` | `#006940` | 임원 보고, 제안서, ISP, 백서 |
| `deloitte-chart` | `theme05` | `#006940` | 데이터·성과 분석, KPI 덱 |
| `deloitte-dark` | `theme06` | `#00A651` | 전략 발표, 아키텍처·토폴로지 |
| `deloitte-light` | `theme01` | `#006940` | 강의 자료, 밝은 톤 요청 |

`deloitte-dark` 만 `PRIMARY_GREEN(#006940)` 대신 `ACCENT_GREEN(#00A651)` 을 씀 — 어두운 배경 위에서 `#006940` 의 명도 대비가 부족함.

`deloitte-light`(theme01)는 84페이지 중 18페이지가 액센트 컨트롤을 노출하지 않으므로, 스탬핑 스크립트의 경고를 확인하여 해당 페이지를 교체해야 함.

## 적용

```bash
# dry-run — 어떤 페이지에 적용되고 어떤 페이지가 미지원인지 확인
node <skill-root>/scripts/apply-deloitte-theme.mjs --goal <deck>/goal.json --preset deloitte-white

# 기록
node <skill-root>/scripts/apply-deloitte-theme.mjs --goal <deck>/goal.json --preset deloitte-white --write
```

`goal.themePack` 이 프리셋의 `basePack` 과 다르면 스크립트가 중단됨 — 테마를 맞추거나 `--force` 를 지정함. 액센트만 다르게 쓰려면 `--accent '#004D2E'` 로 덮어씀.

스탬핑은 `props:safe` 이후, `validate:goal-spec` 이전에 실행함. 렌더 이후에 실행하면 반영되지 않으므로 재렌더가 필요함.

## 팔레트 (형식 불문 공통)

```
PRIMARY_GREEN  #006940   DARK_GREEN  #004D2E   DEEP_GREEN  #0B3B27
ACCENT_GREEN   #00A651   LIME_ACCENT #86BC25   LIGHT_GREEN #E8F5EE
MID_GREEN      #D0EAD8
TEXT_DARK #1A1A1A · TEXT_GRAY #595959 · TEXT_LIGHT #888888
BG_WHITE #FFFFFF · BG_LIGHT #F5F5F5 · BORDER_GRAY #CCCCCC · HEADER_BG #1A1A1A
```

- `LIME_ACCENT(#86BC25)` 는 덱 전체에서 가장 중요한 단 하나의 요소에만 사용함 — 장식 사용 금지
- 그라디언트 금지, 플랫 단색만 사용함
- 삽입 도식(SVG→PNG)과 차트 시리즈 색상도 동일 팔레트를 따름
