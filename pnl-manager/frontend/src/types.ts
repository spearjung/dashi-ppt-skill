/** 백엔드 스키마(§6.2) 대응 타입. */

export type ScreenType =
  | 'contract_info'
  | 'time'
  | 'expense'
  | 'billing'
  | 'wip'
  | 'staffing'
  | 'backlog'
  | 'ltd_adjustment'
  | 'other'

export type UploadStatus = 'uploaded' | 'ocr_done' | 'verifying' | 'confirmed' | 'excluded'

export type ItemType =
  | 'contract_amount'
  | 'time'
  | 'expense'
  | 'os'
  | 'billing'
  | 'net_revenue'
  | 'wip'
  | 'ltd'
  | 'provision'
  | 'backlog_mm'
  | 'rate'

export type Confidence = 'high' | 'medium' | 'low' | 'failed'
export type ValueBasis = 'cumulative' | 'monthly' | 'period'
export type RecordAction = 'confirm' | 'edit' | 'exclude' | 'reassign' | 'duplicate' | 'failed'

export interface Wbs {
  id: number
  contract_id: number
  code: string
  name: string | null
  valid_from: string | null
  valid_to: string | null
}

export interface Contract {
  id: number
  seq: number
  amount: number
  valid_from: string | null
  valid_to: string | null
  note: string | null
  wbs_list: Wbs[]
}

export interface Engagement {
  id: number
  name: string
  client: string
  engagement_code: string
  contract_type: string
  ep: string | null
  em: string | null
  start_date: string | null
  end_date: string | null
  currency: string
  contracts: Contract[]
}

export interface ArithmeticCheck {
  rule: string
  passed: boolean
  diff: number
  row_index: number | null
  message: string | null
  expected: number | null
  actual: number | null
  inputs: Record<string, number>
}

export interface Upload {
  id: number
  engagement_id: number
  original_filename: string | null
  image_hash: string
  screen_type: ScreenType
  screen_type_source: string
  screen_title: string | null
  as_of_date: string | null
  uploaded_by: string | null
  uploaded_at: string
  status: UploadStatus
  unit: string | null
  ocr_provider: string | null
  arithmetic_log: ArithmeticCheck[] | null
  warnings: string[] | null
  duplicate_of_upload_id: number | null
  confirmed_at: string | null
}

export interface UploadResult {
  upload: Upload
  duplicate: boolean
  message: string | null
}

export interface OcrRecord {
  id: number
  upload_id: number
  row_index: number
  field_index: number
  wbs_code_raw: string | null
  wbs_id: number | null
  as_of_date: string | null
  period_from: string | null
  period_to: string | null
  item_type: ItemType
  raw_label: string | null
  amount_raw: string | null
  amount: number | null
  quantity: number | null
  unit: string | null
  value_basis: ValueBasis
  confidence: Confidence
  confidence_reason: string | null
  bbox: number[] | null
  arithmetic_check: ArithmeticCheck | null
  duplicate_verdict: string
  duplicate_of_record_id: number | null
  high_impact: boolean
  needs_individual_confirmation: boolean
}

export interface ConfirmedRecord {
  id: number
  ocr_record_id: number | null
  wbs_id: number | null
  item_type: ItemType
  amount: number | null
  quantity: number | null
  unit: string | null
  period_from: string | null
  period_to: string | null
  value_basis: ValueBasis
  action: RecordAction
  original_amount: number | null
  original_wbs_id: number | null
  confirmed_by: string | null
  confirmed_at: string
  note: string | null
  change_link_id: number | null
}

export interface Gate {
  can_confirm: boolean
  blockers: string[]
  unconfirmed_high_impact: number[]
  unresolved_low: number[]
}

export interface SnapshotComparisonRow {
  ocr_record_id: number
  key: string
  snapshot_amount: number | null
  ocr_amount: number | null
  delta: number | null
}

export interface VerificationView {
  upload: Upload
  records: OcrRecord[]
  confirmed: ConfirmedRecord[]
  arithmetic_log: ArithmeticCheck[]
  snapshot_comparison: {
    snapshot_id: number
    as_of_date: string | null
    rows: SnapshotComparisonRow[]
  } | null
  gate: Gate
}

export interface Decision {
  ocr_record_id: number
  action: RecordAction
  amount?: number | null
  quantity?: number | null
  unit?: string | null
  wbs_id?: number | null
  item_type?: ItemType | null
  value_basis?: ValueBasis | null
  period_from?: string | null
  period_to?: string | null
  note?: string | null
}

export interface WbsResult {
  wbs_id: number
  code: string
  contract_seq: number
  amounts: Partial<Record<ItemType, number>>
  cumulative_usage: number
  billing: number
  current_wip: number
  screen_wip: number | null
  wip_mismatch: number | null
  remaining_mm: number
  remaining_input_estimate: number
  backlog_entered: boolean
  eac: number
  allocated_contract_amount: number
  final_expected_balance: number
  expected_end_wip: number
  ltd_required: number
  ltd_adjusted: number
  ltd_outstanding: number
  unbilled_amount: number
  warnings: string[]
}

export interface ContractResult {
  contract_id: number
  seq: number
  amount: number
  cumulative_usage: number
  eac: number
  balance: number
  final_expected_balance: number
  ltd_required: number
  ltd_adjusted: number
  ltd_outstanding: number
  wbs_ids: number[]
}

export interface Pnl {
  engagement_id: number
  formula_version: string
  snapshot_id: number | null
  total_contract_amount: number
  cumulative_usage: number
  total_billing: number
  current_wip: number
  screen_wip: number | null
  wip_mismatch: number | null
  contract_balance: number
  remaining_input_estimate: number
  backlog_entered: boolean
  provisional: boolean
  eac: number
  final_expected_balance: number
  expected_end_wip: number
  ltd_required: number
  ltd_adjusted: number
  ltd_outstanding: number
  additional_contract_needed: number
  required_mm_reduction: number | null
  weighted_average_rate: number | null
  expected_margin_rate: number | null
  unbilled_amount: number
  contracts: ContractResult[]
  wbs_results: WbsResult[]
  warnings: string[]
}

export interface Snapshot {
  id: number
  engagement_id: number
  as_of_date: string | null
  created_at: string
  upload_ids: number[]
  formula_version: string
  label: string | null
}

export interface SnapshotDiff {
  previous_snapshot_id: number | null
  current_snapshot_id: number
  previous_as_of: string | null
  current_as_of: string | null
  items: Record<string, { previous: number; current: number; delta: number }>
  derived: Record<string, { previous: number | null; current: number | null; delta: number | null }>
  wip_regrowth_after_ltd: boolean
}

export interface Issue {
  id: number
  engagement_id: number
  type: string
  severity: 'high' | 'medium' | 'low'
  title: string
  detail: string | null
  related_record_ids: number[]
  related_wbs_id: number | null
  suggested_actions: { key: string; label: string }[]
  selected_action: string | null
  status: 'open' | 'resolved' | 'dismissed'
  created_at: string
  resolved_at: string | null
}

export interface LtdSummary {
  engagement: {
    ltd_required: number
    contract_balance: number
    eac: number
    final_expected_balance: number
  }
  wbs: {
    wbs_id: number
    code: string
    contract_seq: number
    cumulative_usage: number
    ltd_required: number
    allocated_contract_amount: number
    balance: number
  }[]
  contracts: { seq: number; amount: number; ltd_required: number; balance: number }[]
}

export interface ReclassificationResult {
  issue_id: number
  target_wbs_id?: number
  selected_action?: string
  snapshot_id?: number
  before: LtdSummary
  after: LtdSummary
}

export interface ScenarioParams {
  kind: 'base' | 'best' | 'worst'
  remaining_mm_delta_pct: number
  rate_override: number | null
  end_date_extension_months: number
  additional_contract_amount: number
  expected_expense_os: number | null
}

export interface ScenarioResult {
  kind: string
  params: Omit<ScenarioParams, 'kind'>
  expected_end_wip: number
  ltd_required: number
  additional_contract_needed: number
  required_mm_reduction: number | null
  expected_margin_rate: number | null
  eac: number
  final_expected_balance: number
  total_contract_amount: number
  remaining_input_estimate: number
  provisional: boolean
  warnings: string[]
}

export interface DashboardCounters {
  pending_uploads: number
  unconfirmed_ocr_records: number
  read_failures: number
  duplicate_suspects: number
  wbs_attribution_review: number
}

export interface DashboardProject {
  engagement_id: number
  name: string
  client: string
  engagement_code: string
  ep: string | null
  em: string | null
  contract_type: string
  total_contract_amount: number
  cumulative_usage: number
  remaining_input_estimate: number
  eac: number
  final_expected_balance: number
  expected_margin_rate: number | null
  expected_end_wip: number
  ltd_required: number
  ltd_outstanding: number
  unbilled_amount: number
  provisional: boolean
  backlog_entered: boolean
  latest_snapshot_id: number | null
  latest_snapshot_as_of: string | null
  open_issue_count: number
  warnings: string[]
}

export interface Dashboard {
  counters: DashboardCounters
  projects: DashboardProject[]
  action_required: {
    engagement_id: number
    name: string
    reasons: string[]
    severity: string
  }[]
  latest_snapshot_as_of: string | null
}
