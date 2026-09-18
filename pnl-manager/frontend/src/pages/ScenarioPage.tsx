import { useEffect, useState } from 'react'

import { Empty, ErrorNote, Loading, Money, Panel } from '../components/Common'
import { api } from '../lib/api'
import { krw, mm, pct } from '../lib/format'
import type { ScenarioParams, ScenarioResult } from '../types'

const KINDS: ScenarioParams['kind'][] = ['base', 'best', 'worst']
const KIND_LABELS: Record<string, string> = { base: 'Base', best: 'Best', worst: 'Worst' }

const DEFAULTS: Record<ScenarioParams['kind'], ScenarioParams> = {
  base: {
    kind: 'base',
    remaining_mm_delta_pct: 0,
    rate_override: null,
    end_date_extension_months: 0,
    additional_contract_amount: 0,
    expected_expense_os: null,
  },
  best: {
    kind: 'best',
    remaining_mm_delta_pct: -10,
    rate_override: null,
    end_date_extension_months: 0,
    additional_contract_amount: 0,
    expected_expense_os: null,
  },
  worst: {
    kind: 'worst',
    remaining_mm_delta_pct: 20,
    rate_override: null,
    end_date_extension_months: 1,
    additional_contract_amount: 0,
    expected_expense_os: null,
  },
}

/** 시나리오 계산기(§FR-11). 변수 변경 즉시 재계산한다. */
export function ScenarioPage({ engagementId }: { engagementId: number | null }) {
  const [params, setParams] = useState<Record<ScenarioParams['kind'], ScenarioParams>>(DEFAULTS)
  const [results, setResults] = useState<ScenarioResult[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [saved, setSaved] = useState<string | null>(null)

  useEffect(() => {
    if (!engagementId) return
    let alive = true
    setLoading(true)
    api
      .previewScenarios(engagementId, KINDS.map((kind) => params[kind]))
      .then((rows) => {
        if (alive) {
          setResults(rows)
          setError(null)
        }
      })
      .catch((err: unknown) => {
        if (alive) setError(err instanceof Error ? err.message : String(err))
      })
      .finally(() => {
        if (alive) setLoading(false)
      })
    return () => {
      alive = false
    }
  }, [engagementId, params])

  if (!engagementId) return <Empty message="상단에서 프로젝트를 선택하십시오." />

  function update(kind: ScenarioParams['kind'], patch: Partial<ScenarioParams>) {
    setParams((prev) => ({ ...prev, [kind]: { ...prev[kind], ...patch } }))
    setSaved(null)
  }

  async function save(kind: ScenarioParams['kind']) {
    try {
      await api.saveScenario(engagementId!, params[kind])
      setSaved(`${KIND_LABELS[kind]} 시나리오를 저장했습니다.`)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  const byKind = new Map(results.map((result) => [result.kind, result]))

  return (
    <>
      <Panel title="시나리오 변수" hint="변수를 바꾸면 즉시 재계산됩니다">
        {error && <ErrorNote message={error} />}
        {saved && <div className="alert ok">{saved}</div>}
        <div className="grid cols-3">
          {KINDS.map((kind) => (
            <div key={kind} style={{ border: '1px solid var(--line)', borderRadius: 6, padding: 12 }}>
              <div className="row" style={{ marginBottom: 8 }}>
                <strong>{KIND_LABELS[kind]}</strong>
                <button className="tiny" style={{ marginLeft: 'auto' }} onClick={() => save(kind)}>
                  저장
                </button>
              </div>
              <label className="field">
                잔여 MM 증감률 (%)
                <input
                  className="n"
                  type="number"
                  step={5}
                  value={params[kind].remaining_mm_delta_pct}
                  onChange={(event) =>
                    update(kind, { remaining_mm_delta_pct: Number(event.target.value) })
                  }
                />
              </label>
              <label className="field">
                적용 Rate (원/MM, 비우면 실적 Rate)
                <input
                  className="n"
                  type="number"
                  value={params[kind].rate_override ?? ''}
                  onChange={(event) =>
                    update(kind, {
                      rate_override: event.target.value ? Number(event.target.value) : null,
                    })
                  }
                />
              </label>
              <label className="field">
                종료일 연장 (개월)
                <input
                  className="n"
                  type="number"
                  min={0}
                  value={params[kind].end_date_extension_months}
                  onChange={(event) =>
                    update(kind, { end_date_extension_months: Number(event.target.value) })
                  }
                />
              </label>
              <label className="field">
                추가계약 성사 금액 (원)
                <input
                  className="n"
                  type="number"
                  value={params[kind].additional_contract_amount}
                  onChange={(event) =>
                    update(kind, { additional_contract_amount: Number(event.target.value) })
                  }
                />
              </label>
              <label className="field">
                예상 Expense·OS (원)
                <input
                  className="n"
                  type="number"
                  value={params[kind].expected_expense_os ?? ''}
                  onChange={(event) =>
                    update(kind, {
                      expected_expense_os: event.target.value ? Number(event.target.value) : null,
                    })
                  }
                />
              </label>
            </div>
          ))}
        </div>
      </Panel>

      <Panel title="시나리오별 결과" hint="Base·Best·Worst 동시 비교">
        {loading && results.length === 0 ? (
          <Loading label="계산 중…" />
        ) : (
          <table>
            <thead>
              <tr>
                <th>지표</th>
                {KINDS.map((kind) => (
                  <th key={kind} className="n">
                    {KIND_LABELS[kind]}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              <ResultRow label="총 계약금액" kinds={KINDS} byKind={byKind} pick={(r) => r.total_contract_amount} />
              <ResultRow label="잔여 투입 예상액" kinds={KINDS} byKind={byKind} pick={(r) => r.remaining_input_estimate} />
              <ResultRow label="종료예상 사용액" kinds={KINDS} byKind={byKind} pick={(r) => r.eac} />
              <ResultRow
                label="최종 예상 잔액"
                kinds={KINDS}
                byKind={byKind}
                pick={(r) => r.final_expected_balance}
                money
              />
              <ResultRow label="종료예상 WIP" kinds={KINDS} byKind={byKind} pick={(r) => r.expected_end_wip} />
              <ResultRow label="LTD 필요액" kinds={KINDS} byKind={byKind} pick={(r) => r.ltd_required} />
              <ResultRow
                label="추가계약 필요액"
                kinds={KINDS}
                byKind={byKind}
                pick={(r) => r.additional_contract_needed}
              />
              <tr>
                <td>절감 필요 MM</td>
                {KINDS.map((kind) => (
                  <td key={kind} className="n">
                    {mm(byKind.get(kind)?.required_mm_reduction ?? null)}
                  </td>
                ))}
              </tr>
              <tr>
                <td>예상 손익률</td>
                {KINDS.map((kind) => {
                  const rate = byKind.get(kind)?.expected_margin_rate ?? null
                  return (
                    <td key={kind} className={`n ${(rate ?? 0) < 0 ? 'neg' : ''}`}>
                      {pct(rate)}
                    </td>
                  )
                })}
              </tr>
              <tr>
                <td>Backlog</td>
                {KINDS.map((kind) => (
                  <td key={kind} className="n small">
                    {byKind.get(kind)?.provisional ? (
                      <span className="badge medium">미입력(잠정)</span>
                    ) : (
                      '입력'
                    )}
                  </td>
                ))}
              </tr>
            </tbody>
          </table>
        )}
        <p className="small muted" style={{ marginBottom: 0 }}>
          종료일 연장은 현재 월별 투입 수준이 연장 기간에도 유지된다고 가정해 잔여 MM을 늘립니다.
        </p>
      </Panel>
    </>
  )
}

function ResultRow({
  label,
  kinds,
  byKind,
  pick,
  money = false,
}: {
  label: string
  kinds: ScenarioParams['kind'][]
  byKind: Map<string, ScenarioResult>
  pick: (result: ScenarioResult) => number
  money?: boolean
}) {
  return (
    <tr>
      <td>{label}</td>
      {kinds.map((kind) => {
        const result = byKind.get(kind)
        const value = result ? pick(result) : null
        return (
          <td key={kind} className="n">
            {money ? <Money value={value} /> : krw(value)}
          </td>
        )
      })}
    </tr>
  )
}
