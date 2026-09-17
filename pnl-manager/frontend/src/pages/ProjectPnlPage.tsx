import { useState } from 'react'
import { Link } from 'react-router-dom'

import { Empty, ErrorNote, Loading, Money, Panel, WarningList } from '../components/Common'
import { IssuePanel } from '../components/IssuePanel'
import { api } from '../lib/api'
import { ISSUE_TYPE_LABELS, ITEM_LABELS, krw, mm, pct } from '../lib/format'
import { useAsync } from '../lib/useAsync'

/** 프로젝트 손익 화면(§7). Snapshot 시점 전환과 WBS 오류 후보 조치를 함께 제공한다. */
export function ProjectPnlPage({ engagementId }: { engagementId: number | null }) {
  const [snapshotId, setSnapshotId] = useState<number | null>(null)

  const snapshots = useAsync(
    () => (engagementId ? api.listSnapshots(engagementId) : Promise.resolve([])),
    [engagementId],
  )
  const pnl = useAsync(
    () => (engagementId ? api.getPnl(engagementId, snapshotId) : Promise.resolve(null)),
    [engagementId, snapshotId],
  )
  const issues = useAsync(
    () => (engagementId ? api.listIssues(engagementId) : Promise.resolve([])),
    [engagementId],
  )

  if (!engagementId) return <Empty message="상단에서 프로젝트를 선택하십시오." />
  if (pnl.loading) return <Loading />
  if (pnl.error) return <ErrorNote message={pnl.error} />
  if (!pnl.data) return <Empty message="계산할 확정 데이터가 없습니다." />

  const data = pnl.data
  const openIssues = (issues.data ?? []).filter((issue) => issue.status === 'open')

  function refreshAll() {
    pnl.reload()
    issues.reload()
    snapshots.reload()
  }

  return (
    <>
      <Panel
        title="손익 요약"
        hint={`산식 버전 ${data.formula_version}${data.snapshot_id ? ` · Snapshot #${data.snapshot_id} 시점 재현` : ' · 최신 확정값'}`}
        actions={
          <span className="row">
            <label className="field" style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
              Snapshot 시점
              <select
                value={snapshotId ?? ''}
                onChange={(event) => setSnapshotId(event.target.value ? Number(event.target.value) : null)}
              >
                <option value="">최신 확정값</option>
                {(snapshots.data ?? []).map((snapshot) => (
                  <option key={snapshot.id} value={snapshot.id}>
                    #{snapshot.id} {snapshot.as_of_date ?? ''} {snapshot.label ?? ''}
                  </option>
                ))}
              </select>
            </label>
            <Link to="/scenario">
              <button className="tiny">시나리오 계산기</button>
            </Link>
          </span>
        }
      >
        <ul className="kpis">
          <li>
            <span>총 계약금액</span>
            <b>{krw(data.total_contract_amount)}</b>
          </li>
          <li>
            <span>누적 실적</span>
            <b>{krw(data.cumulative_usage)}</b>
          </li>
          <li>
            <span>잔여 투입 예상액</span>
            <b>{data.backlog_entered ? krw(data.remaining_input_estimate) : '미입력'}</b>
            {!data.backlog_entered && <em>Backlog 미입력</em>}
          </li>
          <li>
            <span>종료예상 사용액</span>
            <b>{krw(data.eac)}</b>
            {data.provisional && <em>잠정치</em>}
          </li>
          <li>
            <span>최종 예상 잔액</span>
            <b>
              <Money value={data.final_expected_balance} />
            </b>
          </li>
          <li>
            <span>예상 손익률</span>
            <b className={(data.expected_margin_rate ?? 0) < 0 ? 'neg' : undefined}>
              {pct(data.expected_margin_rate)}
            </b>
          </li>
          <li>
            <span>현재 WIP</span>
            <b>{krw(data.current_wip)}</b>
            {data.wip_mismatch !== null && data.wip_mismatch !== 0 && (
              <em>화면값과 {krw(data.wip_mismatch)} 차이</em>
            )}
          </li>
          <li>
            <span>종료예상 WIP</span>
            <b>{krw(data.expected_end_wip)}</b>
          </li>
          <li>
            <span>LTD 필요액</span>
            <b>{krw(data.ltd_required)}</b>
            {data.ltd_adjusted > 0 && <em>조정 {krw(data.ltd_adjusted)} 반영 후 {krw(data.ltd_outstanding)}</em>}
          </li>
          <li>
            <span>추가계약 필요액</span>
            <b>{krw(data.additional_contract_needed)}</b>
          </li>
          <li>
            <span>절감 필요 MM</span>
            <b>{mm(data.required_mm_reduction)}</b>
            {data.weighted_average_rate && <em>가중평균 Rate {krw(data.weighted_average_rate)}</em>}
          </li>
          <li>
            <span>미청구액</span>
            <b>{krw(data.unbilled_amount)}</b>
          </li>
        </ul>
        <WarningList title="검증 경고" items={data.warnings} />
      </Panel>

      <Panel title="계약 차수별" hint="차수 간 잔액으로 초과분을 상계하지 않습니다">
        <table>
          <thead>
            <tr>
              <th>차수</th>
              <th className="n">계약금액</th>
              <th className="n">누적 사용액</th>
              <th className="n">계약 잔액</th>
              <th className="n">종료예상액</th>
              <th className="n">최종 예상잔액</th>
              <th className="n">LTD 필요액</th>
              <th className="n">LTD 조정</th>
              <th className="n">LTD 잔여</th>
            </tr>
          </thead>
          <tbody>
            {data.contracts.map((contract) => (
              <tr key={contract.contract_id}>
                <td>{contract.seq === 0 ? '최초(0차)' : `${contract.seq}차 변경`}</td>
                <td className="n">{krw(contract.amount)}</td>
                <td className="n">{krw(contract.cumulative_usage)}</td>
                <td className="n">
                  <Money value={contract.balance} />
                </td>
                <td className="n">{krw(contract.eac)}</td>
                <td className="n">
                  <Money value={contract.final_expected_balance} />
                </td>
                <td className="n">{krw(contract.ltd_required)}</td>
                <td className="n">{krw(contract.ltd_adjusted)}</td>
                <td className="n">{krw(contract.ltd_outstanding)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>

      <Panel title="WBS별 상세">
        <div style={{ overflowX: 'auto' }}>
          <table>
            <thead>
              <tr>
                <th>WBS</th>
                <th>차수</th>
                <th className="n">계약금액(배분)</th>
                <th className="n">Time</th>
                <th className="n">Expense</th>
                <th className="n">OS</th>
                <th className="n">누적 사용액</th>
                <th className="n">Billing</th>
                <th className="n">현재 WIP</th>
                <th className="n">잔여 MM</th>
                <th className="n">잔여 투입</th>
                <th className="n">종료예상액</th>
                <th className="n">최종 예상잔액</th>
                <th className="n">LTD 필요액</th>
                <th className="n">미청구</th>
              </tr>
            </thead>
            <tbody>
              {data.wbs_results.map((row) => (
                <tr key={row.wbs_id}>
                  <td className="mono">{row.code}</td>
                  <td>{row.contract_seq}차</td>
                  <td className="n">{krw(row.allocated_contract_amount)}</td>
                  <td className="n">{krw(row.amounts.time ?? 0)}</td>
                  <td className="n">{krw(row.amounts.expense ?? 0)}</td>
                  <td className="n">{krw(row.amounts.os ?? 0)}</td>
                  <td className="n">{krw(row.cumulative_usage)}</td>
                  <td className="n">{krw(row.billing)}</td>
                  <td className="n">
                    {krw(row.current_wip)}
                    {row.wip_mismatch !== null && row.wip_mismatch !== 0 && (
                      <span className="badge low" style={{ marginLeft: 3 }}>
                        불일치
                      </span>
                    )}
                  </td>
                  <td className="n">{row.backlog_entered ? row.remaining_mm : '-'}</td>
                  <td className="n">
                    {row.backlog_entered ? krw(row.remaining_input_estimate) : <span className="badge medium">미입력</span>}
                  </td>
                  <td className="n">{krw(row.eac)}</td>
                  <td className="n">
                    <Money value={row.final_expected_balance} />
                  </td>
                  <td className="n">{krw(row.ltd_required)}</td>
                  <td className="n">{krw(row.unbilled_amount)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      <Panel title="Billing 현황">
        <table>
          <thead>
            <tr>
              <th>WBS</th>
              <th className="n">누적 사용액</th>
              <th className="n">Billing</th>
              <th className="n">미청구액</th>
              <th className="n">종료예상 WIP</th>
            </tr>
          </thead>
          <tbody>
            {data.wbs_results.map((row) => (
              <tr key={row.wbs_id}>
                <td className="mono">{row.code}</td>
                <td className="n">{krw(row.cumulative_usage)}</td>
                <td className="n">{krw(row.billing)}</td>
                <td className="n">{krw(row.unbilled_amount)}</td>
                <td className="n">{krw(row.expected_end_wip)}</td>
              </tr>
            ))}
            <tr>
              <th>합계</th>
              <th className="n">{krw(data.cumulative_usage)}</th>
              <th className="n">{krw(data.total_billing)}</th>
              <th className="n">{krw(data.unbilled_amount)}</th>
              <th className="n">{krw(data.expected_end_wip)}</th>
            </tr>
          </tbody>
        </table>
      </Panel>

      <Panel
        title="WBS 오류 후보·이상징후·조치사항"
        hint={`미해결 ${openIssues.length}건`}
        actions={<button className="tiny" onClick={refreshAll}>새로고침</button>}
      >
        {issues.loading ? (
          <Loading />
        ) : openIssues.length === 0 ? (
          <Empty message="미해결 이상징후가 없습니다." />
        ) : (
          openIssues.map((issue) => (
            <IssuePanel
              key={issue.id}
              issue={issue}
              wbsResults={data.wbs_results}
              typeLabel={ISSUE_TYPE_LABELS[issue.type] ?? issue.type}
              onResolved={refreshAll}
            />
          ))
        )}
      </Panel>

      <Panel title="Snapshot 이력" hint="확정 시점마다 누적 보존되며 덮어쓰지 않습니다">
        {(snapshots.data ?? []).length === 0 ? (
          <Empty message="Snapshot이 없습니다." />
        ) : (
          <table>
            <thead>
              <tr>
                <th className="n">#</th>
                <th>기준일</th>
                <th>생성 시각</th>
                <th>설명</th>
                <th>산식</th>
                <th className="n">Upload</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {(snapshots.data ?? []).map((snapshot) => (
                <tr key={snapshot.id}>
                  <td className="n">{snapshot.id}</td>
                  <td>{snapshot.as_of_date ?? '-'}</td>
                  <td className="small">{new Date(snapshot.created_at).toLocaleString('ko-KR')}</td>
                  <td className="small">{snapshot.label ?? '-'}</td>
                  <td className="small mono">{snapshot.formula_version}</td>
                  <td className="n small">{snapshot.upload_ids.length}</td>
                  <td>
                    <button className="tiny" onClick={() => setSnapshotId(snapshot.id)}>
                      이 시점으로 보기
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>

      <Panel title="항목 구성" hint="화면 항목명 기준 확정값">
        <table>
          <thead>
            <tr>
              <th>WBS</th>
              {Object.keys(ITEM_LABELS).map((item) => (
                <th key={item} className="n">
                  {ITEM_LABELS[item]}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.wbs_results.map((row) => (
              <tr key={row.wbs_id}>
                <td className="mono">{row.code}</td>
                {Object.keys(ITEM_LABELS).map((item) => (
                  <td key={item} className="n">
                    {row.amounts[item as keyof typeof row.amounts] === undefined
                      ? '-'
                      : krw(row.amounts[item as keyof typeof row.amounts]!)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>
    </>
  )
}
