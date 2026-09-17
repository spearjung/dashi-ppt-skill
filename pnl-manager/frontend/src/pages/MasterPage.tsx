import { useState } from 'react'

import { Empty, ErrorNote, Loading, Panel } from '../components/Common'
import { api } from '../lib/api'
import { krw } from '../lib/format'
import { useAsync } from '../lib/useAsync'
import type { Engagement } from '../types'

/** 프로젝트 마스터 화면(§7). Engagement·계약 차수·WBS 등록과 유효기간 겹침 검사. */
export function MasterPage({
  engagementId,
  onChanged,
}: {
  engagementId: number | null
  onChanged: () => void
}) {
  const engagement = useAsync(
    () => (engagementId ? api.getEngagement(engagementId) : Promise.resolve(null)),
    [engagementId],
  )
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  function handle(promise: Promise<unknown>, message: string) {
    setError(null)
    setNotice(null)
    return promise
      .then(() => {
        setNotice(message)
        engagement.reload()
        onChanged()
      })
      .catch((err: unknown) => setError(err instanceof Error ? err.message : String(err)))
  }

  return (
    <>
      {error && <ErrorNote message={error} />}
      {notice && <div className="alert ok">{notice}</div>}

      <NewEngagementForm onSubmit={(payload) => handle(api.createEngagement(payload), '프로젝트를 생성했습니다.')} />

      {engagementId === null ? (
        <Empty message="프로젝트를 생성하거나 상단에서 선택하십시오." />
      ) : engagement.loading ? (
        <Loading />
      ) : engagement.data ? (
        <ExistingEngagement data={engagement.data} handle={handle} />
      ) : null}
    </>
  )
}

function ExistingEngagement({
  data,
  handle,
}: {
  data: Engagement
  handle: (promise: Promise<unknown>, message: string) => Promise<void>
}) {
  const [contractSeq, setContractSeq] = useState(String(data.contracts.length))
  const [amount, setAmount] = useState('')
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [wbsCode, setWbsCode] = useState('')
  const [wbsContractId, setWbsContractId] = useState<number | ''>(data.contracts[0]?.id ?? '')
  const [staffWbsId, setStaffWbsId] = useState<number | ''>('')
  const [remainingMm, setRemainingMm] = useState('')
  const [rate, setRate] = useState('')
  const [month, setMonth] = useState('')

  const allWbs = data.contracts.flatMap((contract) => contract.wbs_list)

  return (
    <>
      <Panel
        title={`${data.engagement_code} · ${data.name}`}
        hint={`${data.client} · ${data.contract_type} · EP ${data.ep ?? '-'} / EM ${data.em ?? '-'} · ${data.start_date ?? '-'} ~ ${data.end_date ?? '-'}`}
      >
        <table>
          <thead>
            <tr>
              <th>차수</th>
              <th className="n">계약금액</th>
              <th>유효기간</th>
              <th>WBS Code (유효기간 상속)</th>
            </tr>
          </thead>
          <tbody>
            {data.contracts.length === 0 ? (
              <tr>
                <td colSpan={4} className="muted small">
                  등록된 계약 차수가 없습니다.
                </td>
              </tr>
            ) : (
              data.contracts.map((contract) => (
                <tr key={contract.id}>
                  <td>{contract.seq === 0 ? '최초(0차)' : `${contract.seq}차 변경`}</td>
                  <td className="n">{krw(contract.amount)}</td>
                  <td className="small">
                    {contract.valid_from ?? '-'} ~ {contract.valid_to ?? '-'}
                  </td>
                  <td className="small">
                    {contract.wbs_list.length === 0 ? (
                      <span className="muted">없음</span>
                    ) : (
                      contract.wbs_list.map((wbs) => (
                        <div key={wbs.id} className="mono">
                          {wbs.code}
                          <span className="muted small">
                            {' '}
                            ({wbs.valid_from ?? '-'} ~ {wbs.valid_to ?? '-'})
                          </span>
                        </div>
                      ))
                    )}
                  </td>
                </tr>
              ))
            )}
            <tr>
              <th>총 계약금액</th>
              <th className="n">{krw(data.contracts.reduce((sum, c) => sum + c.amount, 0))}</th>
              <th colSpan={2} />
            </tr>
          </tbody>
        </table>
      </Panel>

      <div className="grid cols-2">
        <Panel title="계약 차수 추가" hint="유효기간이 기존 차수와 겹치면 거부됩니다">
          <div className="row">
            <label className="field">
              차수
              <input className="n" style={{ width: 60 }} value={contractSeq} onChange={(e) => setContractSeq(e.target.value)} />
            </label>
            <label className="field">
              계약금액(원)
              <input className="n" value={amount} onChange={(e) => setAmount(e.target.value)} />
            </label>
            <label className="field">
              유효 시작일
              <input type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
            </label>
            <label className="field">
              유효 종료일
              <input type="date" value={to} onChange={(e) => setTo(e.target.value)} />
            </label>
            <button
              style={{ alignSelf: 'flex-end' }}
              onClick={() =>
                handle(
                  api.addContract(data.id, {
                    seq: Number(contractSeq),
                    amount: Number(amount.replace(/,/g, '')) || 0,
                    valid_from: from || null,
                    valid_to: to || null,
                    wbs_list: [],
                  }),
                  '계약 차수를 추가했습니다.',
                )
              }
            >
              추가
            </button>
          </div>
        </Panel>

        <Panel title="WBS Code 등록" hint="계약 차수의 유효기간을 상속합니다">
          <div className="row">
            <label className="field">
              계약 차수
              <select value={wbsContractId} onChange={(e) => setWbsContractId(Number(e.target.value))}>
                <option value="">선택</option>
                {data.contracts.map((contract) => (
                  <option key={contract.id} value={contract.id}>
                    {contract.seq}차
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              WBS Code
              <input
                className="mono"
                style={{ width: 210 }}
                placeholder="KOR01434-01-01"
                value={wbsCode}
                onChange={(e) => setWbsCode(e.target.value)}
              />
            </label>
            <button
              style={{ alignSelf: 'flex-end' }}
              disabled={wbsContractId === '' || !wbsCode}
              onClick={() =>
                handle(
                  api.addWbs(Number(wbsContractId), { code: wbsCode, name: null }),
                  'WBS Code를 등록했습니다.',
                )
              }
            >
              등록
            </button>
          </div>
        </Panel>
      </div>

      <Panel
        title="잔여 투입 계획 직접 입력"
        hint="Backlog 화면을 캡처하지 못한 경우 사용합니다. 미입력 시 종료예상값은 잠정치로 표시됩니다"
      >
        <div className="row">
          <label className="field">
            WBS
            <select value={staffWbsId} onChange={(e) => setStaffWbsId(Number(e.target.value))}>
              <option value="">선택</option>
              {allWbs.map((wbs) => (
                <option key={wbs.id} value={wbs.id}>
                  {wbs.code}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            월 (YYYY-MM)
            <input style={{ width: 96 }} placeholder="2025-11" value={month} onChange={(e) => setMonth(e.target.value)} />
          </label>
          <label className="field">
            잔여 MM
            <input className="n" style={{ width: 84 }} value={remainingMm} onChange={(e) => setRemainingMm(e.target.value)} />
          </label>
          <label className="field">
            적용 Rate (원/MM)
            <input className="n" value={rate} onChange={(e) => setRate(e.target.value)} />
          </label>
          <button
            style={{ alignSelf: 'flex-end' }}
            disabled={staffWbsId === ''}
            onClick={() =>
              handle(
                api.saveStaffing(data.id, [
                  {
                    wbs_id: Number(staffWbsId),
                    month: month || null,
                    remaining_mm: Number(remainingMm) || 0,
                    rate: Number(rate.replace(/,/g, '')) || 0,
                  },
                ]),
                '잔여 투입 계획을 추가했습니다.',
              )
            }
          >
            추가
          </button>
        </div>
      </Panel>
    </>
  )
}

function NewEngagementForm({ onSubmit }: { onSubmit: (payload: unknown) => Promise<void> }) {
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState({
    name: '',
    client: '',
    engagement_code: '',
    contract_type: 'fixed_price',
    ep: '',
    em: '',
    start_date: '',
    end_date: '',
    first_amount: '',
    first_wbs: '',
  })

  const set = (key: keyof typeof form) => (event: { target: { value: string } }) =>
    setForm((prev) => ({ ...prev, [key]: event.target.value }))

  if (!open) {
    return (
      <Panel title="프로젝트 마스터">
        <button className="primary" onClick={() => setOpen(true)}>
          새 프로젝트 생성
        </button>
        <span className="small muted" style={{ marginLeft: 8 }}>
          최초 1회 등록합니다. Engagement Code·계약기간·최초 계약금액·WBS Code가 필요합니다.
        </span>
      </Panel>
    )
  }

  return (
    <Panel title="새 프로젝트 생성" hint="최초 1회 등록">
      <div className="row">
        <label className="field">
          프로젝트명
          <input value={form.name} onChange={set('name')} />
        </label>
        <label className="field">
          고객사
          <input value={form.client} onChange={set('client')} />
        </label>
        <label className="field">
          Engagement Code
          <input className="mono" placeholder="KOR01434" value={form.engagement_code} onChange={set('engagement_code')} />
        </label>
        <label className="field">
          계약유형
          <select value={form.contract_type} onChange={set('contract_type')}>
            <option value="fixed_price">고정가</option>
            <option value="time_and_material">T&amp;M</option>
            <option value="other">기타</option>
          </select>
        </label>
      </div>
      <div className="row" style={{ marginTop: 8 }}>
        <label className="field">
          EP
          <input value={form.ep} onChange={set('ep')} />
        </label>
        <label className="field">
          EM
          <input value={form.em} onChange={set('em')} />
        </label>
        <label className="field">
          계약 시작일
          <input type="date" value={form.start_date} onChange={set('start_date')} />
        </label>
        <label className="field">
          계약 종료일
          <input type="date" value={form.end_date} onChange={set('end_date')} />
        </label>
        <label className="field">
          최초 계약금액(원)
          <input className="n" value={form.first_amount} onChange={set('first_amount')} />
        </label>
        <label className="field">
          최초 WBS Code
          <input className="mono" value={form.first_wbs} onChange={set('first_wbs')} />
        </label>
      </div>
      <div className="row end" style={{ marginTop: 10 }}>
        <button onClick={() => setOpen(false)}>취소</button>
        <button
          className="primary"
          disabled={!form.name || !form.client || !form.engagement_code}
          onClick={() =>
            void onSubmit({
              name: form.name,
              client: form.client,
              engagement_code: form.engagement_code,
              contract_type: form.contract_type,
              ep: form.ep || null,
              em: form.em || null,
              start_date: form.start_date || null,
              end_date: form.end_date || null,
              currency: 'KRW',
              contracts: [
                {
                  seq: 0,
                  amount: Number(form.first_amount.replace(/,/g, '')) || 0,
                  valid_from: form.start_date || null,
                  valid_to: form.end_date || null,
                  wbs_list: form.first_wbs ? [{ code: form.first_wbs, name: '최초 계약 WBS' }] : [],
                },
              ],
            }).then(() => setOpen(false))
          }
        >
          생성
        </button>
      </div>
    </Panel>
  )
}
