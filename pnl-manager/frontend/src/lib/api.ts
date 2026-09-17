/** 백엔드 REST 클라이언트. 모든 오류는 한국어 메시지로 변환해 던진다. */

import type {
  Dashboard,
  Decision,
  Engagement,
  Issue,
  Pnl,
  ReclassificationResult,
  ScenarioParams,
  ScenarioResult,
  Snapshot,
  SnapshotDiff,
  Upload,
  UploadResult,
  VerificationView,
  Wbs,
} from '../types'

const BASE = '/api'

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message)
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    ...init,
    headers:
      init?.body instanceof FormData
        ? init?.headers
        : { 'Content-Type': 'application/json', ...init?.headers },
  })
  if (!response.ok) {
    let detail = `요청이 실패했습니다 (HTTP ${response.status})`
    try {
      const body = (await response.json()) as { detail?: unknown }
      if (typeof body.detail === 'string') detail = body.detail
      else if (body.detail) detail = JSON.stringify(body.detail)
    } catch {
      /* 본문이 JSON이 아닌 경우 기본 메시지 사용 */
    }
    throw new ApiError(detail, response.status)
  }
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export const api = {
  health: () => request<{ status: string; formula_version: string; ocr_provider: string }>('/health'),

  // 프로젝트 마스터
  listEngagements: () => request<Engagement[]>('/engagements'),
  getEngagement: (id: number) => request<Engagement>(`/engagements/${id}`),
  createEngagement: (payload: unknown) =>
    request<Engagement>('/engagements', { method: 'POST', body: JSON.stringify(payload) }),
  addContract: (engagementId: number, payload: unknown) =>
    request<unknown>(`/engagements/${engagementId}/contracts`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  addWbs: (contractId: number, payload: unknown) =>
    request<Wbs>(`/contracts/${contractId}/wbs`, { method: 'POST', body: JSON.stringify(payload) }),
  listWbs: (engagementId: number) => request<Wbs[]>(`/engagements/${engagementId}/wbs`),
  saveStaffing: (engagementId: number, rows: unknown[]) =>
    request<{ created: number }>(`/engagements/${engagementId}/staffing`, {
      method: 'POST',
      body: JSON.stringify(rows),
    }),

  // 업로드·판독
  uploadCaptures: (engagementId: number, files: File[], screenType?: string, uploadedBy?: string) => {
    const form = new FormData()
    files.forEach((file) => form.append('files', file))
    if (screenType) form.append('screen_type', screenType)
    if (uploadedBy) form.append('uploaded_by', uploadedBy)
    return request<UploadResult[]>(`/engagements/${engagementId}/uploads`, {
      method: 'POST',
      body: form,
    })
  },
  listUploads: (engagementId: number) => request<Upload[]>(`/engagements/${engagementId}/uploads`),
  setScreenType: (uploadId: number, screenType: string) =>
    request<Upload>(`/uploads/${uploadId}/screen-type`, {
      method: 'PATCH',
      body: JSON.stringify({ screen_type: screenType }),
    }),
  runOcr: (uploadId: number) => request<Upload>(`/uploads/${uploadId}/ocr`, { method: 'POST' }),
  injectPayload: (uploadId: number, payload: unknown) =>
    request<Upload>(`/uploads/${uploadId}/ocr-payload`, {
      method: 'POST',
      body: JSON.stringify({ payload }),
    }),
  imageUrl: (uploadId: number) => `${BASE}/uploads/${uploadId}/image`,

  // 검증·확정
  getVerification: (uploadId: number) => request<VerificationView>(`/uploads/${uploadId}/verification`),
  applyDecisions: (uploadId: number, decisions: Decision[], actor?: string) =>
    request<VerificationView>(`/uploads/${uploadId}/decisions`, {
      method: 'POST',
      body: JSON.stringify({ decisions, actor }),
    }),
  addManualRecord: (uploadId: number, payload: unknown) =>
    request<VerificationView>(`/uploads/${uploadId}/manual-records`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  confirmUpload: (uploadId: number, actor?: string) =>
    request<{
      upload: Upload
      snapshot_id: number | null
      issues_created: number
      diff: SnapshotDiff | null
      pnl: Pnl | null
    }>(`/uploads/${uploadId}/confirm`, {
      method: 'POST',
      body: JSON.stringify({ actor, create_snapshot: true }),
    }),

  // 계산·Snapshot
  getPnl: (engagementId: number, snapshotId?: number | null) =>
    request<Pnl>(
      `/engagements/${engagementId}/pnl${snapshotId ? `?snapshot_id=${snapshotId}` : ''}`,
    ),
  listSnapshots: (engagementId: number) => request<Snapshot[]>(`/engagements/${engagementId}/snapshots`),
  getSnapshotDiff: (snapshotId: number) => request<SnapshotDiff>(`/snapshots/${snapshotId}/diff`),

  // 시나리오
  getScenarios: (engagementId: number) =>
    request<ScenarioResult[]>(`/engagements/${engagementId}/scenarios`),
  previewScenarios: (engagementId: number, params: ScenarioParams[]) =>
    request<ScenarioResult[]>(`/engagements/${engagementId}/scenarios/preview`, {
      method: 'POST',
      body: JSON.stringify(params),
    }),
  saveScenario: (engagementId: number, params: ScenarioParams) =>
    request<unknown>(`/engagements/${engagementId}/scenarios`, {
      method: 'POST',
      body: JSON.stringify(params),
    }),

  // 이상징후·조치
  listIssues: (engagementId: number) => request<Issue[]>(`/engagements/${engagementId}/issues`),
  previewReclassification: (issueId: number, targetWbsId: number) =>
    request<ReclassificationResult>(
      `/issues/${issueId}/reclassification-preview?target_wbs_id=${targetWbsId}`,
    ),
  resolveIssue: (issueId: number, selectedAction: string, targetWbsId?: number, actor?: string) =>
    request<ReclassificationResult>(`/issues/${issueId}/resolve`, {
      method: 'POST',
      body: JSON.stringify({ selected_action: selectedAction, target_wbs_id: targetWbsId, actor }),
    }),

  // 대시보드
  getDashboard: () => request<Dashboard>('/dashboard'),
}
