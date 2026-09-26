import { ITEM_LABELS, krw, signed } from '../lib/format'
import type { SnapshotDiff as Diff } from '../types'
import { Panel } from './Common'

const DERIVED_LABELS: Record<string, string> = {
  eac: '종료예상 사용액',
  final_expected_balance: '최종 예상 잔액',
  expected_end_wip: '종료예상 WIP',
  ltd_required: 'LTD 필요액',
  remaining_input_estimate: '잔여 투입 예상액',
}

/** 연속 Snapshot 간 증감 비교(§FR-08). */
export function SnapshotDiffView({ diff, title = 'Snapshot 비교' }: { diff: Diff; title?: string }) {
  const items = Object.entries(diff.items)
  const derived = Object.entries(diff.derived).filter(([, value]) => value.current !== null)

  return (
    <Panel
      title={title}
      hint={`#${diff.previous_snapshot_id ?? '-'} (${diff.previous_as_of ?? '-'}) → #${diff.current_snapshot_id} (${diff.current_as_of ?? '-'})`}
    >
      {diff.wip_regrowth_after_ltd && (
        <div className="alert">LTD 조정 후 WIP가 다시 증가했습니다. 재발생 원인을 확인하십시오.</div>
      )}
      <div className="grid cols-2">
        <table className="diff-table">
          <thead>
            <tr>
              <th>항목</th>
              <th className="n">이전</th>
              <th className="n">현재</th>
              <th className="n">증감</th>
            </tr>
          </thead>
          <tbody>
            {items.length === 0 ? (
              <tr>
                <td colSpan={4} className="muted small">
                  비교할 항목이 없습니다.
                </td>
              </tr>
            ) : (
              items.map(([item, value]) => (
                <tr key={item}>
                  <td>{ITEM_LABELS[item] ?? item}</td>
                  <td className="n">{krw(value.previous)}</td>
                  <td className="n">{krw(value.current)}</td>
                  <td className={`n ${value.delta > 0 ? 'delta-pos' : value.delta < 0 ? 'delta-neg' : ''}`}>
                    {signed(value.delta)}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
        <table className="diff-table">
          <thead>
            <tr>
              <th>파생값</th>
              <th className="n">이전</th>
              <th className="n">현재</th>
              <th className="n">증감</th>
            </tr>
          </thead>
          <tbody>
            {derived.map(([key, value]) => (
              <tr key={key}>
                <td>{DERIVED_LABELS[key] ?? key}</td>
                <td className="n">{krw(value.previous)}</td>
                <td className="n">{krw(value.current)}</td>
                <td
                  className={`n ${
                    (value.delta ?? 0) > 0 ? 'delta-pos' : (value.delta ?? 0) < 0 ? 'delta-neg' : ''
                  }`}
                >
                  {signed(value.delta)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  )
}
