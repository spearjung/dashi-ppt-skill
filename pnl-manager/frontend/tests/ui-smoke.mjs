/**
 * UI 스모크 테스트.
 *
 * 실행 전제: 백엔드(8000)와 프런트엔드(5173)가 떠 있고, DB에 데모 데이터가
 * 있어야 한다. 데모 데이터는 backend/scripts/seed_demo.py --reset 으로 만든다.
 *
 *   node tests/ui-smoke.mjs
 *
 * §12 수용 기준의 핵심 값이 실제 화면에 표시되는지 확인한다.
 */

import { chromium } from 'playwright'

const BASE = process.env.PNL_WEB_URL ?? 'http://127.0.0.1:5173'
const CHROMIUM = process.env.CHROMIUM_PATH ?? '/opt/pw-browsers/chromium'
const SHOTS = process.env.SHOTS ?? null

const checks = []
const httpFailures = []

function check(name, condition, detail = '') {
  checks.push({ name, ok: Boolean(condition), detail })
  console.log(`${condition ? 'PASS' : 'FAIL'}  ${name}${detail ? ` — ${detail}` : ''}`)
}

const browser = await chromium.launch({ executablePath: CHROMIUM })
const page = await browser.newPage({ viewport: { width: 1500, height: 1000 } })
page.on('response', (r) => {
  if (r.status() >= 400) httpFailures.push(`${r.status()} ${r.url()}`)
})
page.on('pageerror', (e) => httpFailures.push(`pageerror: ${e.message}`))

const shot = async (name) => {
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/${name}.png`, fullPage: true })
}

const panel = (title) => page.locator('.panel', { has: page.locator(`h2:has-text("${title}")`) })

async function confirmAllRows(uploadId) {
  await page.goto(`${BASE}/verify/${uploadId}`, { waitUntil: 'networkidle' })
  await page.waitForSelector('table tbody tr')
  const count = await page.locator('table tbody tr').count()
  for (let i = 0; i < count; i++) {
    const button = page.locator('table tbody tr').nth(i).locator('button.tiny:has-text("확인")').first()
    if (await button.count()) {
      await button.click()
      await page.waitForTimeout(200)
    }
  }
  await page.waitForTimeout(400)
}

try {
  // ── Dashboard: 처리 대기 카운터
  await page.goto(`${BASE}/dashboard`, { waitUntil: 'networkidle' })
  await page.waitForSelector('.counter')
  const counters = await page.locator('.counter b').allTextContents()
  check('대시보드 카운터가 표시된다', counters.length >= 5, counters.join('/'))
  check(
    'WBS 귀속 검토 건수가 1건 이상',
    Number(counters[3]) >= 1,
    `WBS 귀속 검토 ${counters[3]}건`,
  )
  await shot('01-dashboard')

  // ── 검증 화면: 고영향 필드 확정 차단
  await page.goto(`${BASE}/verify/1`, { waitUntil: 'networkidle' })
  await page.waitForSelector('.image-pane img')
  check('원본 캡처가 표시된다', await page.locator('.image-pane img').isVisible())
  check(
    '고영향 필드 미확인 시 최종 확정이 차단된다',
    await page.locator('button.primary:has-text("최종 확정")').isDisabled(),
  )
  check('확정 차단 사유가 노출된다', (await page.locator('text=확정 차단 사유').count()) > 0)

  const arithmetic = await panel('산술 교차검증').innerText()
  check('산술 교차검증이 통과로 표시된다', arithmetic.includes('9,895,867') && arithmetic.includes('통과'))
  await shot('02-verify')

  // ── 값별 액션: 수정 시 원본 판독값 병기
  const editRow = page.locator('table tbody tr').nth(2)
  await editRow.locator('input[placeholder="수정 금액(원)"]').fill('9000000')
  await editRow.locator('button.tiny:has-text("수정")').click()
  await page.waitForTimeout(500)
  check('수정 셀이 원본 판독값을 함께 표시한다', (await editRow.innerText()).includes('원본'))
  check('수정 셀이 색상으로 구분된다', (await editRow.getAttribute('class'))?.includes('edited'))
  await editRow.locator('button.tiny:has-text("확인")').first().click()
  await page.waitForTimeout(400)

  // ── 두 업로드 확정
  await confirmAllRows(1)
  check(
    '모든 값 확인 후 확정이 가능해진다',
    !(await page.locator('button.primary:has-text("최종 확정")').isDisabled()),
  )
  await page.locator('button.primary:has-text("최종 확정")').click()
  await page.waitForTimeout(1200)
  await confirmAllRows(2)
  await page.locator('button.primary:has-text("최종 확정")').click()
  await page.waitForTimeout(1200)

  // ── 프로젝트 손익: 재분류 전 LTD
  await page.goto(`${BASE}/pnl`, { waitUntil: 'networkidle' })
  await page.waitForSelector('.kpis')
  const before = await panel('WBS별 상세').innerText()
  check('재분류 전 1차 WBS 예상 LTD 41,858,114원', before.includes('41,858,114'))
  check('재분류 전 2차 WBS 예상 LTD 27,629,160원', before.includes('27,629,160'))
  const summary = await panel('손익 요약').innerText()
  check('Backlog 미입력이 잠정치로 표시된다', summary.includes('잠정치') && summary.includes('미입력'))
  await shot('03-pnl-before')

  // ── 재분류 미리보기: §12.2-4 기대값
  await page.locator('button.tiny:has-text("전·후 재계산 미리보기")').click()
  await page.waitForTimeout(900)
  const issuePanel = await panel('WBS 오류 후보').innerText()
  check('미리보기 후 1차 WBS 예상 LTD 31,962,247원', issuePanel.includes('31,962,247'))
  check('미리보기 후 2차 WBS 예상 LTD 37,525,027원', issuePanel.includes('37,525,027'))
  check('미리보기는 값을 변경하지 않는다', issuePanel.includes('값은 아직 변경되지 않았습니다'))
  const stillBefore = await panel('WBS별 상세').innerText()
  check('미리보기 중 WBS별 상세는 재분류 전 값을 유지한다', stillBefore.includes('41,858,114'))
  await shot('04-reclass-preview')

  // ── 재분류 조치 적용
  await page.locator('button.tiny:has-text("2차 WBS로 재분류")').click()
  await page.waitForTimeout(1500)
  await page.reload({ waitUntil: 'networkidle' })
  await page.waitForSelector('.kpis')
  const after = await panel('WBS별 상세').innerText()
  check('재분류 후 1차 WBS 예상 LTD 31,962,247원', after.includes('31,962,247'))
  check('재분류 후 2차 WBS 예상 LTD 37,525,027원', after.includes('37,525,027'))
  const snapshots = await panel('Snapshot 이력').locator('tbody tr').count()
  check('재분류 전·후 Snapshot이 누적 보존된다', snapshots >= 3, `${snapshots}건`)
  await shot('05-pnl-after')

  // ── 조치사항 라벨이 한국어인지
  const issueText = await panel('WBS 오류 후보').innerText()
  check('조치 라벨에 원시 키가 노출되지 않는다', !/request_change_order|book_ltd|issue_invoice/.test(issueText))

  // ── 시나리오: Backlog가 입력된 프로젝트
  await page.selectOption('.engagement-picker', { index: 1 })
  await page.click('text=시나리오')
  await page.waitForSelector('.grid.cols-3')
  await page.waitForTimeout(1000)
  const scenarioBefore = await page.locator('table').last().innerText()
  await page.locator('input[type=number]').first().fill('-30')
  await page.waitForTimeout(1000)
  const scenarioAfter = await page.locator('table').last().innerText()
  check('변수 변경 시 시나리오가 즉시 재계산된다', scenarioBefore !== scenarioAfter)
  check('Worst 시나리오에 LTD·절감 필요 MM이 산출된다', scenarioAfter.includes('MM'))
  await shot('06-scenario')

  // ── 포트폴리오 대시보드
  await page.click('text=Dashboard')
  await page.waitForSelector('.counter')
  const rows = await panel('프로젝트별 최종 예상손익').locator('tbody tr').count()
  check('포트폴리오에 다중 프로젝트가 표시된다', rows >= 2, `${rows}개`)
  await shot('07-portfolio')

  check('HTTP·JS 오류가 없다', httpFailures.length === 0, httpFailures.join(' | '))
} finally {
  await browser.close()
}

const failed = checks.filter((c) => !c.ok)
console.log(`\n${checks.length - failed.length}/${checks.length} 통과`)
if (failed.length > 0) {
  console.error(`실패: ${failed.map((c) => c.name).join(', ')}`)
  process.exit(1)
}
