import { useState } from 'react'

import { api } from '../lib/api'
import { krw, signed } from '../lib/format'
import type { Issue, ReclassificationResult, WbsResult } from '../types'
import { ErrorNote } from './Common'

/**
 * 이상징후 1건과 제안 조치(§FR-09).
 * 재분류 선택 시 관련 WBS의 예상 LTD·계약 잔액을 즉시 재계산해 전·후를 나란히 표시한다.
 */
export function IssuePanel({
  issue,
  wbsResults,
  typeLabel,
  onResolved,
}: {
  issue: Issue
  wbsResults: WbsResult[]
  typeLabel: string
  onResolved: () => void
}) {
  const [targetWbsId, setTargetWbsId] = useState<number | ''>(() => {
    // 기본 재분류 대상은 현재 WBS보다 다음 차수의 첫 WBS로 제안한다.
    const current = wbsResults.find((row) => row.wbs_id === issue.related_wbs_id)
    const next = wbsResults.find((row) => (current ? row.contract_seq > current.contract_seq : false))
    return next?.wbs_id ?? ''
  })
  const [preview, setPreview] = useState<ReclassificationResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const needsTarget = (action: string) => action === 'reassign_to_next_wbs'

  async function loadPreview() {
    if (targetWbsId === '') {
      setError('재분류 대상 WBS를 선택하십시오.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      setPreview(await api.previewReclassification(issue.id, targetWbsId))
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  async function resolve(action: string) {
    if (needsTarget(action) && targetWbsId === '') {
      setError('재분류 대상 WBS를 선택하십시오.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      const result = await api.resolveIssue(
        issue.id,
        action,
        needsTarget(action) && targetWbsId !== '' ? targetWbsId : undefined,
        'EP',
      )
      setPreview(result)
      onResolved()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div
      style={{
        border: '1px solid var(--line)',
        borderRadius: 'var(--radius)',
        padding: 12,
        marginBottom: 10,
      }}
    >
      <div className="row">
        <span className={`badge ${issue.severity === 'high' ? 'low' : 'medium'}`}>{typeLabel}</span>
        <strong>{issue.title}</strong>
        <span className="small muted" style={{ marginLeft: 'auto' }}>
          Issue #{issue.id} · 관련 레코드 {issue.related_record_ids.length}건
        </span>
      </div>
      {issue.detail && <p className="small" style={{ margin: '6px 0' }}>{issue.detail}</p>}
      {error && <ErrorNote message={error} />}

      <div className="row" style={{ marginTop: 6 }}>
        {issue.suggested_actions.some((action) => needsTarget(action.key)) && (
          <>
            <label className="field" style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
              재분류 대상
              <select
                value={targetWbsId}
                onChange={(event) => setTargetWbsId(event.target.value ? Number(event.target.value) : '')}
              >
                <option value="">선택</option>
                {wbsResults.map((row) => (
                  <option key={row.wbs_id} value={row.wbs_id}>
                    {row.code} ({row.contract_seq}차)
                  </option>
                ))}
              </select>
            </label>
            <button className="tiny" disabled={busy} onClick={loadPreview}>
              전·후 재계산 미리보기
            </button>
          </>
        )}
        {issue.suggested_actions.map((action) => (
          <button key={action.key} className="tiny" disabled={busy} onClick={() => resolve(action.key)}>
            {action.label}
          </button>
        ))}
      </div>

      {preview && <BeforeAfter result={preview} />}
    </div>
  )
}

function BeforeAfter({ result }: { result: ReclassificationResult }) {
  const beforeByCode = new Map(result.before.wbs.map((row) => [row.code, row]))

  return (
    <div style={{ marginTop: 10 }}>
      <p className="small muted" style={{ margin: '0 0 4px' }}>
        {result.selected_action
          ? `조치 적용 완료${result.snapshot_id ? ` · Snapshot #${result.snapshot_id} 생성` : ''}`
          : '미리보기 — 값은 아직 변경되지 않았습니다.'}
      </p>
      <table className="diff-table">
        <thead>
          <tr>
            <th>WBS</th>
            <th className="n">전 누적 사용액</th>
            <th className="n">후 누적 사용액</th>
            <th className="n">전 예상 LTD</th>
            <th className="n">후 예상 LTD</th>
            <th className="n">LTD 증감</th>
            <th className="n">후 계약 잔액</th>
          </tr>
        </thead>
        <tbody>
          {result.after.wbs.map((row) => {
            const before = beforeByCode.get(row.code)
            const delta = row.ltd_required - (before?.ltd_required ?? 0)
            return (
              <tr key={row.code}>
                <td className="mono">
                  {row.code} <span className="muted small">({row.contract_seq}차)</span>
                </td>
                <td className="n">{krw(before?.cumulative_usage ?? null)}</td>
                <td className="n">{krw(row.cumulative_usage)}</td>
                <td className="n">{krw(before?.ltd_required ?? null)}</td>
                <td className="n">
                  <strong>{krw(row.ltd_required)}</strong>
                </td>
                <td className={`n ${delta > 0 ? 'delta-pos' : delta < 0 ? 'delta-neg' : ''}`}>
                  {signed(delta)}
                </td>
                <td className="n">{krw(row.balance)}</td>
              </tr>
            )
          })}
          <tr>
            <th>프로젝트 합계</th>
            <th className="n">{krw(result.before.engagement.eac)}</th>
            <th className="n">{krw(result.after.engagement.eac)}</th>
            <th className="n">{krw(result.before.engagement.ltd_required)}</th>
            <th className="n">{krw(result.after.engagement.ltd_required)}</th>
            <th className="n">
              {signed(result.after.engagement.ltd_required - result.before.engagement.ltd_required)}
            </th>
            <th className="n">{krw(result.after.engagement.contract_balance)}</th>
          </tr>
        </tbody>
      </table>
    </div>
  )
}
