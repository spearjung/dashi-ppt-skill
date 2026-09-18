import { useState } from 'react'

import {
  ACTION_LABELS,
  BASIS_LABELS,
  CONFIDENCE_LABELS,
  DUPLICATE_LABELS,
  ITEM_LABELS,
  krw,
} from '../lib/format'
import type { ConfirmedRecord, Decision, OcrRecord, RecordAction, Wbs } from '../types'

const ACTIONS: RecordAction[] = ['confirm', 'edit', 'exclude', 'reassign', 'duplicate', 'failed']

/**
 * 판독 결과 편집 표(§FR-05).
 * 값별 액션 6종을 적용하고, 수정 셀은 색상으로 구분하며 원본 판독값을 함께 표시한다.
 */
export function EditableTable({
  records,
  confirmed,
  wbsList,
  onApply,
  onHover,
  busy,
}: {
  records: OcrRecord[]
  confirmed: ConfirmedRecord[]
  wbsList: Wbs[]
  onApply: (decisions: Decision[]) => void
  onHover: (recordId: number | null) => void
  busy: boolean
}) {
  const [drafts, setDrafts] = useState<Record<number, { amount?: string; wbsId?: number }>>({})
  const confirmedByRecord = new Map(confirmed.map((row) => [row.ocr_record_id, row]))

  const batchable = records.filter(
    (record) => !record.needs_individual_confirmation && !confirmedByRecord.has(record.id),
  )

  function rowClass(record: OcrRecord): string {
    const decision = confirmedByRecord.get(record.id)
    if (!decision) {
      return record.confidence === 'low' || record.confidence === 'failed' ? 'blocked' : ''
    }
    if (decision.action === 'edit') return 'edited'
    if (decision.action === 'exclude') return 'excluded'
    if (decision.action === 'reassign') return 'reassigned'
    if (decision.action === 'duplicate') return 'duplicated'
    return ''
  }

  function apply(record: OcrRecord, action: RecordAction) {
    const draft = drafts[record.id] ?? {}
    const decision: Decision = { ocr_record_id: record.id, action }
    if (action === 'edit') {
      const parsed = Number((draft.amount ?? '').replace(/,/g, ''))
      if (!Number.isFinite(parsed)) {
        window.alert('수정 금액을 원 단위 정수로 입력하십시오.')
        return
      }
      decision.amount = parsed
    }
    if (action === 'reassign') {
      const targetId = draft.wbsId ?? record.wbs_id
      if (!targetId) {
        window.alert('재분류 대상 WBS를 선택하십시오.')
        return
      }
      decision.wbs_id = targetId
    }
    onApply([decision])
  }

  return (
    <div>
      <div className="row" style={{ marginBottom: 8 }}>
        <button
          disabled={busy || batchable.length === 0}
          onClick={() => onApply(batchable.map((record) => ({ ocr_record_id: record.id, action: 'confirm' })))}
          title="고영향 필드와 Medium 이하 신뢰도 필드는 일괄 확인 대상에서 제외됩니다"
        >
          일괄 확인 ({batchable.length}건)
        </button>
        <span className="small muted">
          고영향 필드(계약금액·Time·Expense·Billing·LTD·날짜·단위·WBS Code)는 개별 확인이 필요합니다.
        </span>
      </div>

      <div style={{ overflowX: 'auto' }}>
        <table>
          <thead>
            <tr>
              <th className="n">행</th>
              <th>WBS</th>
              <th>항목</th>
              <th>화면 항목명</th>
              <th className="n">판독값</th>
              <th>기준</th>
              <th>조회기간</th>
              <th>신뢰도</th>
              <th>중복</th>
              <th>상태</th>
              <th style={{ minWidth: 260 }}>액션</th>
            </tr>
          </thead>
          <tbody>
            {records.map((record) => {
              const decision = confirmedByRecord.get(record.id)
              const draft = drafts[record.id] ?? {}
              return (
                <tr
                  key={record.id}
                  className={rowClass(record)}
                  onMouseEnter={() => onHover(record.id)}
                  onMouseLeave={() => onHover(null)}
                >
                  <td className="n">{record.row_index}</td>
                  <td className="small nowrap">
                    {wbsList.find((wbs) => wbs.id === (decision?.wbs_id ?? record.wbs_id))?.code ?? (
                      <span className="badge low">미매칭</span>
                    )}
                    {record.wbs_code_raw && (
                      <span className="original mono">판독: {record.wbs_code_raw}</span>
                    )}
                  </td>
                  <td className="small">
                    {ITEM_LABELS[record.item_type] ?? record.item_type}
                    {record.high_impact && (
                      <span className="badge impact" style={{ marginLeft: 3 }}>
                        고영향
                      </span>
                    )}
                  </td>
                  <td className="small mono">{record.raw_label ?? '-'}</td>
                  <td className="n">
                    {decision && decision.action === 'edit' ? (
                      <>
                        <strong>{krw(decision.amount)}</strong>
                        <span className="original">원본 {krw(record.amount)}</span>
                      </>
                    ) : record.amount !== null ? (
                      krw(record.amount)
                    ) : record.quantity !== null ? (
                      record.quantity
                    ) : (
                      <span className="badge failed">판독 불가</span>
                    )}
                    {record.unit && record.unit !== 'KRW' && (
                      <span className="original">단위 {record.unit}</span>
                    )}
                  </td>
                  <td className="small">{BASIS_LABELS[record.value_basis] ?? record.value_basis}</td>
                  <td className="small nowrap">
                    {record.period_from ?? '-'} ~ {record.period_to ?? '-'}
                  </td>
                  <td>
                    <span className={`badge ${record.confidence}`}>
                      {CONFIDENCE_LABELS[record.confidence]}
                    </span>
                    {record.confidence_reason && (
                      <span className="original" title={record.confidence_reason}>
                        {record.confidence_reason.length > 26
                          ? `${record.confidence_reason.slice(0, 26)}…`
                          : record.confidence_reason}
                      </span>
                    )}
                  </td>
                  <td className="small">
                    {record.duplicate_verdict !== 'new' && (
                      <span className="badge dup">{DUPLICATE_LABELS[record.duplicate_verdict]}</span>
                    )}
                  </td>
                  <td className="small nowrap">
                    {decision ? (
                      <>
                        <span className="badge high">{ACTION_LABELS[decision.action]}</span>
                        <span className="original">{decision.confirmed_by ?? ''}</span>
                      </>
                    ) : (
                      <span className="muted">미확인</span>
                    )}
                  </td>
                  <td>
                    <div className="row">
                      {ACTIONS.map((action) => (
                        <button
                          key={action}
                          className={`tiny${decision?.action === action ? ' active' : ''}`}
                          disabled={busy}
                          onClick={() => apply(record, action)}
                          title={
                            action === 'failed'
                              ? '판독 실패로 표시합니다. 확정하려면 값을 직접 입력해야 합니다.'
                              : undefined
                          }
                        >
                          {ACTION_LABELS[action]}
                        </button>
                      ))}
                    </div>
                    <div className="row" style={{ marginTop: 4 }}>
                      <input
                        className="n small"
                        style={{ width: 118 }}
                        placeholder="수정 금액(원)"
                        value={draft.amount ?? ''}
                        onChange={(event) =>
                          setDrafts((prev) => ({
                            ...prev,
                            [record.id]: { ...prev[record.id], amount: event.target.value },
                          }))
                        }
                      />
                      <select
                        className="small"
                        value={draft.wbsId ?? record.wbs_id ?? ''}
                        onChange={(event) =>
                          setDrafts((prev) => ({
                            ...prev,
                            [record.id]: { ...prev[record.id], wbsId: Number(event.target.value) },
                          }))
                        }
                      >
                        <option value="">재분류 대상 WBS</option>
                        {wbsList.map((wbs) => (
                          <option key={wbs.id} value={wbs.id}>
                            {wbs.code}
                          </option>
                        ))}
                      </select>
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
