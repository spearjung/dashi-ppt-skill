/**
 * 웹 배포 형태(단일 오리진 + 공용 비밀번호 인증) 스모크 테스트.
 *
 * 실행 전제: 프런트엔드를 빌드한 뒤 백엔드를 배포와 같은 설정으로 띄운다.
 *
 *   cd frontend && npm run build
 *   cd ../backend && PNL_STATIC_DIR=../frontend/dist \
 *     PNL_APP_PASSWORD=demo-password-1234 PNL_SECURE_COOKIES=0 \
 *     PNL_DATA_DIR=/tmp/pnl-web PNL_CORS_ORIGINS="" \
 *     uvicorn app.main:app --port 8100
 *   cd ../frontend && node tests/auth-smoke.mjs
 *
 * 데모 데이터가 필요하다: python scripts/seed_demo.py --reset
 */

import { chromium } from 'playwright'
const BASE = process.env.PNL_WEB_URL ?? 'http://127.0.0.1:8100'
const OUT = process.env.SHOTS ?? null
const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' })
const page = await browser.newPage({ viewport: { width: 1400, height: 900 } })
const fails = []
page.on('pageerror', (e) => fails.push(`pageerror: ${e.message}`))
page.on('response', (r) => { if (r.status() >= 400 && r.status() !== 401) fails.push(`${r.status()} ${r.url()}`) })
const results = []
const check = (n, c, d = '') => {
  results.push({ name: n, ok: Boolean(c) })
  console.log(`${c ? 'PASS' : 'FAIL'}  ${n}${d ? ` — ${d}` : ''}`)
}

await page.goto(BASE, { waitUntil: 'networkidle' })
check('로그인 화면이 먼저 표시된다', await page.locator('.login-card').isVisible())
check('이름·비밀번호를 함께 입력받는다',
  (await page.locator('.login-card input').count()) === 2)
if (OUT) await page.screenshot({ path: `${OUT}/01-login.png`, fullPage: true })

// 잘못된 비밀번호
await page.fill('.login-card input[autocomplete="name"]', '정창모')
await page.fill('.login-card input[type=password]', 'wrong-password')
await page.click('.login-card button')
await page.waitForTimeout(600)
check('틀린 비밀번호는 오류로 안내된다',
  (await page.locator('.login-card .alert.error').innerText()).includes('비밀번호'))
if (OUT) await page.screenshot({ path: `${OUT}/02-login-error.png`, fullPage: true })

// 정상 로그인
await page.fill('.login-card input[type=password]', 'demo-password-1234')
await page.click('.login-card button')
await page.waitForSelector('.topbar', { timeout: 10000 })
await page.waitForTimeout(800)
check('로그인 후 대시보드로 진입한다', await page.locator('.counter').first().isVisible())
check('상단에 로그인한 이름이 표시된다',
  (await page.locator('.topbar .session').innerText()).includes('정창모'))
if (OUT) await page.screenshot({ path: `${OUT}/03-dashboard.png`, fullPage: true })

// 세션 쿠키가 HttpOnly 인지 — 문서 JS로 읽히지 않아야 한다
const visibleToJs = await page.evaluate(() => document.cookie.includes('pnl_session'))
check('세션 쿠키가 JS에 노출되지 않는다(HttpOnly)', visibleToJs === false)

// 확정 기록 행위자가 로그인 이름으로 남는지
await page.goto(`${BASE}/verify/1`, { waitUntil: 'networkidle' })
await page.waitForSelector('table tbody tr')
const rows = await page.locator('table tbody tr').count()
for (let i = 0; i < rows; i++) {
  const b = page.locator('table tbody tr').nth(i).locator('button.tiny:has-text("확인")').first()
  if (await b.count()) { await b.click(); await page.waitForTimeout(200) }
}
await page.waitForTimeout(500)
const table = await page.locator('table').first().innerText()
check('확정 기록의 행위자가 로그인 이름이다', table.includes('정창모'), '검증 표의 상태 열')
if (OUT) await page.screenshot({ path: `${OUT}/04-verify-actor.png`, fullPage: true })

// 로그아웃 → 다시 로그인 화면
await page.goto(BASE, { waitUntil: 'networkidle' })
await page.click('.topbar .session button')
await page.waitForSelector('.login-card', { timeout: 10000 })
check('로그아웃하면 로그인 화면으로 돌아간다', await page.locator('.login-card').isVisible())

check('HTTP·JS 오류가 없다', fails.length === 0, fails.join(' | '))
await browser.close()

const failed = results.filter((r) => !r.ok)
console.log(`\n${results.length - failed.length}/${results.length} 통과`)
if (failed.length > 0) {
  console.error(`실패: ${failed.map((r) => r.name).join(', ')}`)
  process.exit(1)
}
