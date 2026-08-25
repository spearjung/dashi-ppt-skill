#!/usr/bin/env node
// James Report × Dashi PPT — 딜로이트 그린 액센트 스탬핑.
//
// goal.json 의 모든 template variant 에 프리셋 액센트 색상을 써 넣음. 액센트 컨트롤을
// 노출하지 않는 레이아웃은 경고로 보고함(해당 페이지는 다른 레이아웃으로 교체해야 함).
//
//   node apply-deloitte-theme.mjs --goal <deck>/goal.json [--preset deloitte-white] [--write]
//
// 옵션:
//   --goal <path>      대상 goal.json (필수)
//   --preset <name>    themes/deloitte-green.json 의 프리셋 키 (기본: default 프리셋)
//   --accent <hex>     프리셋 액센트를 덮어씀
//   --project <path>   dashi-ppt 생성기 project 디렉터리 (기본: 형제 스킬에서 자동 탐색)
//   --write            변경을 파일에 기록 (미지정 시 dry-run)
//   --force            goal.themePack 이 프리셋 basePack 과 달라도 진행

import { readFile, writeFile } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const SKILL_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const PRESET_FILE = path.join(SKILL_ROOT, 'themes', 'deloitte-green.json');
const ACCENT_CONTROL_KEYS = new Set(['accentColor', 'accent']);

function parseArgs(argv) {
  const args = { write: false, force: false };
  for (let i = 0; i < argv.length; i += 1) {
    const token = argv[i];
    if (token === '--write') args.write = true;
    else if (token === '--force') args.force = true;
    else if (token.startsWith('--')) args[token.slice(2)] = argv[++i];
  }
  return args;
}

function resolveProjectDir(explicit) {
  const candidates = [
    explicit,
    path.resolve(SKILL_ROOT, '..', 'dashi-ppt', 'project'),
    path.resolve(SKILL_ROOT, '..', '..', 'dashi-ppt', 'project'),
  ].filter(Boolean);
  for (const dir of candidates) {
    if (existsSync(path.join(dir, 'src', 'components', 'themes', 'generated-metadata.js'))) return dir;
  }
  throw new Error(
    'dashi-ppt project 디렉터리를 찾지 못함. --project <path> 로 명시할 것 '
    + `(탐색: ${candidates.join(', ')})`,
  );
}

// layoutKey -> 해당 레이아웃이 노출하는 액센트 컨트롤 key ( 없으면 미수록 )
async function loadAccentControlMap(projectDir) {
  const metadataPath = path.join(projectDir, 'src', 'components', 'themes', 'generated-metadata.js');
  const { GENERATED_THEME_PAGES } = await import(pathToFileURL(metadataPath).href);
  const map = new Map();
  for (const entry of GENERATED_THEME_PAGES) {
    const page = entry.page || entry;
    const controls = entry.controls || page.controls || [];
    const accent = controls.find(c => c.type === 'color' && ACCENT_CONTROL_KEYS.has(c.publicKey || c.key));
    if (accent) map.set(page.key, accent.publicKey || accent.key);
  }
  return map;
}

// schemaVersion 1(단일 layout)과 2(variants 배열)를 모두 훑음.
function* eachTemplateVariant(goal) {
  for (const [slideIndex, slide] of (goal.slides || []).entries()) {
    const variants = Array.isArray(slide.variants) ? slide.variants : null;
    if (variants) {
      for (const variant of variants) {
        if (variant?.kind === 'bespoke') continue;
        if (variant?.layout) yield { slideIndex, id: variant.id || variant.layout, holder: variant };
      }
    } else if (slide?.layout) {
      yield { slideIndex, id: slide.id || slide.layout, holder: slide };
    }
  }
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.goal) throw new Error('--goal <path> 가 필요함');

  const presetFile = JSON.parse(await readFile(PRESET_FILE, 'utf8'));
  const presetName = args.preset
    || Object.entries(presetFile.presets).find(([, p]) => p.default)?.[0];
  const preset = presetFile.presets[presetName];
  if (!preset) {
    throw new Error(`알 수 없는 프리셋 "${presetName}". 사용 가능: ${Object.keys(presetFile.presets).join(', ')}`);
  }
  const accent = args.accent || preset.accent;
  if (!/^#[0-9a-fA-F]{6}$/.test(accent)) throw new Error(`액센트 색상이 6자리 hex 가 아님: ${accent}`);

  const goalPath = path.resolve(args.goal);
  const goal = JSON.parse(await readFile(goalPath, 'utf8'));

  if (goal.themePack && goal.themePack !== preset.basePack && !args.force) {
    throw new Error(
      `goal.themePack("${goal.themePack}") 이 프리셋 "${presetName}" 의 basePack("${preset.basePack}") 과 다름. `
      + '테마를 맞추거나 --force 를 지정할 것',
    );
  }

  const accentControls = await loadAccentControlMap(resolveProjectDir(args.project));

  let stamped = 0;
  let unchanged = 0;
  const unsupported = [];
  const unknown = [];

  for (const { slideIndex, id, holder } of eachTemplateVariant(goal)) {
    const controlKey = accentControls.get(holder.layout);
    if (!controlKey) {
      (accentControls.size && holder.layout.includes('_page') ? unsupported : unknown)
        .push(`slide ${slideIndex + 1} / ${id} / ${holder.layout}`);
      continue;
    }
    holder.props ||= {};
    if (holder.props[controlKey] === accent) unchanged += 1;
    else {
      holder.props[controlKey] = accent;
      stamped += 1;
    }
  }

  console.log(`preset       : ${presetName} (base ${preset.basePack})`);
  console.log(`accent       : ${accent}`);
  console.log(`stamped      : ${stamped}`);
  console.log(`already set  : ${unchanged}`);

  if (unknown.length) {
    console.log(`\n[오류] 메타데이터에 없는 레이아웃 ${unknown.length}건:`);
    for (const line of unknown) console.log(`  - ${line}`);
  }
  if (unsupported.length) {
    console.log(`\n[경고] 액센트 컨트롤이 없어 딜로이트 그린이 적용되지 않는 레이아웃 ${unsupported.length}건:`);
    for (const line of unsupported) console.log(`  - ${line}`);
    console.log('  → 액센트 컨트롤이 있는 레이아웃으로 교체할 것');
  }

  if (args.write) {
    if (stamped) {
      await writeFile(goalPath, `${JSON.stringify(goal, null, 2)}\n`, 'utf8');
      console.log(`\n기록 완료: ${goalPath}`);
    } else {
      console.log('\n변경 없음 — 기록 생략');
    }
  } else {
    console.log('\ndry-run — 기록하려면 --write 를 지정할 것');
  }

  process.exitCode = unknown.length || unsupported.length ? 1 : 0;
}

main().catch(error => {
  console.error(`apply-deloitte-theme: ${error.message}`);
  process.exit(2);
});
