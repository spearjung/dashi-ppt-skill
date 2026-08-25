#!/usr/bin/env node
// James Report × Dashi PPT — goal.json 문안 강제 검증기.
//
// james-report 원칙 0(ZERO META/ZERO OBVIOUS)·2(액션 타이틀)·3(개조식 국문)을
// dashi-ppt goal.json 의 문안 필드에 대해 기계 검증함.
//
//   node lint-zero-meta.mjs <deck>/goal.json [--warn-only] [--json]
//
// 종료 코드: 0 위반 없음 / 1 error 존재 / 2 실행 실패

import { readFile } from 'node:fs/promises';

// validate-goal-spec.mjs 와 동일한 비문안(non-content) 필드 판정.
const NON_CONTENT_KEY = /^(id|key|type|kind|tone|color|colour|accent|fill|stroke|background|bg|tint|hex|variant|style|theme|mode|layout|align|side|position|icon|href|url|src|fit|className|source|fields|schemaVersion|themePack|randomSeed|workflowRunId|selectedVariant|compositionFamily|role|priority|adjustable|language)$/i;
const NON_CONTENT_PATH = /(^|\.)(contentMap|controls|media|mediaSlots|preview|grid|designIntent)(\.|\[|$)/;

// 원칙 0 — 문서가 자기 자신을 설명하는 표현.
const META_PATTERNS = [
  { re: /기준\s*문서/, msg: '출처·버전 메타 라인' },
  { re: /범위\s*·/, msg: '범위 메타 라인' },
  { re: /본\s*(자료|보고서|덱|장표|문서)(는|은)/, msg: '문서 자기 참조' },
  { re: /이\s*(보고서|덱|자료|문서)(는|은)/, msg: '문서 자기 참조' },
  { re: /클릭\s*시/, msg: '내비게이션 안내' },
  { re: /읽는\s*법/, msg: '읽는 법 안내' },
  { re: /한눈에/, msg: '구조 서술 상투구' },
  { re: /이후\s*(다룸|다룬다|설명)/, msg: '크로스레퍼런스' },
  { re: /(아래|위|왼쪽|오른쪽|좌측|우측)\s*(그림|도식|표)\s*참조/, msg: '도식 크로스레퍼런스' },
  { re: /(을|를)\s*다룬다/, msg: '구조 서술' },
  { re: /(에서|에)\s*다룸/, msg: '크로스레퍼런스' },
  { re: /(을|를)\s*(제안함|제시함|정리함|소개함)/, msg: '보고 행위 서술' },
  { re: /(을|를)\s*(정리한|담은)\s*(자료|내용)/, msg: '내용 요약형 서술' },
  { re: /작업\s*보드/, msg: '금지 상투구' },
  { re: /(축은|의\s*실체)/, msg: '금지 상투구' },
];

// 원칙 3 — 개조식 종결 위반(경어체·평서형).
const STYLE_PATTERNS = [
  { re: /(합니다|습니다|입니다|십시오|하세요|어요|예요)\s*[.!?]?$/, msg: '경어체 종결 — 개조식(~임/~함/~됨)으로 교정' },
  { re: /(한다|된다|이다|있다|없다|간다|본다|짓는다|만든다)\s*[.!?]?$/, msg: '평서형 종결 — 개조식(~임/~함/~됨)으로 교정' },
];

// 원칙 3 — AI-tell 장식 기호.
const DECORATION_RE = /[⚠→←↑↓✓✔✕✖★☆]|(?:^|\s)[×!](?:\s|$)/;

// dashi-ppt 템플릿 기본 문안 잔여.
const TEMPLATE_LEFTOVERS = [
  'AI Capital', 'SoundWave', '声浪', 'Key Metrics', 'End of Report',
  '请输入文本', '感谢阅读', 'Lorem ipsum',
];

const HAN_ONLY_RE = /^[^가-힣]*[一-鿿][^가-힣]*$/;

// 원칙 3 — 페이지 코드는 P-prefix, S-prefix 금지.
const S_PREFIX_RE = /(^|\s)S\d+(\s*[\/·]|\s|$)/;

// 최상위 goal 은 생성기 지시문이라 슬라이드에 노출되지 않음 — 문체 검사 대상에서 제외.
const SKIP_ROOT_KEYS = new Set(['goal', 'audience', 'owner']);

// 액션 타이틀이 아닌 명사구 제목의 흔한 꼬리.
const NOUN_TITLE_TAIL = /(방안|전략|계획|개요|소개|현황|체계|구성|정의|배경|목적|범위|일정)\s*$/;

const findings = [];
function report(level, path, value, msg) {
  findings.push({ level, path, msg, value: value.length > 120 ? `${value.slice(0, 117)}…` : value });
}

function isTitlePath(p) { return /(^|\.)(title|titleShort|headline|heading)$/i.test(p); }
function isCoverSummaryPath(p) { return /^slides\[0\]\..*\b(summary|subtitle|lead)$/i.test(p); }

function walk(node, path, ctx) {
  if (typeof node === 'string') {
    lintString(node, path, ctx);
    return;
  }
  if (Array.isArray(node)) {
    node.forEach((item, i) => walk(item, `${path}[${i}]`, ctx));
    return;
  }
  if (node && typeof node === 'object') {
    for (const [key, value] of Object.entries(node)) {
      if (NON_CONTENT_KEY.test(key)) continue;
      if (!path && SKIP_ROOT_KEYS.has(key)) continue;
      const next = path ? `${path}.${key}` : key;
      if (NON_CONTENT_PATH.test(next)) continue;
      walk(value, next, ctx);
    }
  }
}

function lintString(text, path, ctx) {
  const value = text.trim();
  if (!value) return;

  for (const { re, msg } of META_PATTERNS) {
    if (re.test(value)) report('error', path, value, `ZERO META 위반 — ${msg}`);
  }
  for (const leftover of TEMPLATE_LEFTOVERS) {
    if (value.includes(leftover)) report('error', path, value, `템플릿 기본 문안 잔여 — "${leftover}"`);
  }
  if (/[가-힣]/.test(value)) {
    for (const { re, msg } of STYLE_PATTERNS) {
      if (re.test(value)) report('error', path, value, `개조식 위반 — ${msg}`);
    }
  }
  if (DECORATION_RE.test(value)) {
    report('warn', path, value, '장식 기호 — 수식 용례가 아니면 제거');
  }
  if (value.length > 3 && HAN_ONLY_RE.test(value)) {
    report('warn', path, value, '한글 없는 한자 문안 — 중국어 기본 문안 잔여 가능성');
  }
  if (/(^|\.)(pageLabel|pageCode|footer|kicker)$/i.test(path) && S_PREFIX_RE.test(value)) {
    report('error', path, value, '페이지 코드 S-prefix — P-prefix(P1, P2…)로 교정');
  }
  if (isTitlePath(path) && NOUN_TITLE_TAIL.test(value)) {
    report('warn', path, value, '명사구 제목 — 결론 문장(액션 타이틀)으로 교정');
  }
  if (isCoverSummaryPath(path) && ctx.goalText && value === ctx.goalText) {
    report('error', path, value, '커버 서브타이틀이 goal 필드 복사 — so-what 주장으로 교체');
  }
}

async function main() {
  const argv = process.argv.slice(2);
  const warnOnly = argv.includes('--warn-only');
  const asJson = argv.includes('--json');
  const target = argv.find(a => !a.startsWith('--'));
  if (!target) throw new Error('사용법: lint-zero-meta.mjs <goal.json> [--warn-only] [--json]');

  const goal = JSON.parse(await readFile(target, 'utf8'));
  walk(goal, '', { goalText: typeof goal.goal === 'string' ? goal.goal.trim() : '' });

  const errors = findings.filter(f => f.level === 'error');
  const warns = findings.filter(f => f.level === 'warn');

  if (asJson) {
    console.log(JSON.stringify({ target, errors, warns }, null, 2));
  } else {
    for (const f of [...errors, ...warns]) {
      console.log(`${f.level === 'error' ? 'ERROR' : 'WARN '}  ${f.path}\n        ${f.msg}\n        "${f.value}"`);
    }
    console.log(`\n${target} — error ${errors.length}건 / warn ${warns.length}건`);
    if (!errors.length && !warns.length) console.log('ZERO META·개조식 검증 통과');
  }

  process.exitCode = !warnOnly && errors.length ? 1 : 0;
}

main().catch(error => {
  console.error(`lint-zero-meta: ${error.message}`);
  process.exit(2);
});
