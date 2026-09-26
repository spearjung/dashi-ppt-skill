/** 표시 형식. 저장은 원(KRW) 정수이고 표시 시점에만 단위를 변환한다(§9). */

export function krw(amount: number | null | undefined): string {
  if (amount === null || amount === undefined) return '-'
  return amount.toLocaleString('ko-KR')
}

/** 큰 금액을 백만원 단위로 축약해 표시한다. */
export function krwShort(amount: number | null | undefined): string {
  if (amount === null || amount === undefined) return '-'
  const abs = Math.abs(amount)
  if (abs >= 100_000_000) return `${(amount / 100_000_000).toFixed(1)}억`
  if (abs >= 1_000_000) return `${Math.round(amount / 1_000_000).toLocaleString('ko-KR')}백만`
  return amount.toLocaleString('ko-KR')
}

export function pct(rate: number | null | undefined): string {
  if (rate === null || rate === undefined) return '-'
  return `${(rate * 100).toFixed(1)}%`
}

export function mm(value: number | null | undefined): string {
  if (value === null || value === undefined) return '-'
  return `${value.toLocaleString('ko-KR', { maximumFractionDigits: 2 })} MM`
}

export function signed(amount: number | null | undefined): string {
  if (amount === null || amount === undefined) return '-'
  const sign = amount > 0 ? '+' : ''
  return `${sign}${amount.toLocaleString('ko-KR')}`
}

export const ITEM_LABELS: Record<string, string> = {
  contract_amount: '계약금액',
  time: 'Time',
  expense: 'Expense',
  os: 'OS(외주)',
  billing: 'Billing',
  net_revenue: 'Net Revenue',
  wip: 'WIP',
  ltd: 'LTD',
  provision: 'Provision',
  backlog_mm: '잔여 MM',
  rate: '적용 Rate',
  billing_planned: '청구 예정액',
  billing_unbilled: '미청구액',
  billable_expense: '청구가능 경비',
}

export const SCREEN_LABELS: Record<string, string> = {
  contract_info: '계약정보',
  time: 'Time',
  expense: 'Expense',
  billing: 'Billing',
  wip: 'WIP',
  staffing: 'Staffing',
  backlog: 'Backlog',
  ltd_adjustment: 'LTD Adjustment',
  other: '기타',
}

export const CONFIDENCE_LABELS: Record<string, string> = {
  high: 'High',
  medium: 'Medium',
  low: 'Low',
  failed: 'Failed',
}

export const ACTION_LABELS: Record<string, string> = {
  confirm: '확인',
  edit: '수정',
  exclude: '제외',
  reassign: '재분류',
  duplicate: '중복 표시',
  failed: '판독 실패',
}

export const BASIS_LABELS: Record<string, string> = {
  cumulative: '누적',
  monthly: '월 발생',
  period: '기간',
}

export const DUPLICATE_LABELS: Record<string, string> = {
  new: '신규',
  exact_duplicate: '중복(Key 8종 동일)',
  latest_snapshot_candidate: '최신 Snapshot 후보',
  separate_period: '별도 기간',
  basis_conflict: '값 기준 충돌',
  change_link: '수정 전·후',
}

export const ISSUE_TYPE_LABELS: Record<string, string> = {
  period_error: '기간 오류',
  wbs_attribution: 'WBS 귀속 오류',
  duplicate: '중복',
  unit_error: '단위 오류',
  total_mismatch: '합계 불일치',
  billing_action: 'Billing 조치',
  wip_action: 'WIP 조치',
  backlog_missing: 'Backlog 미입력',
}
