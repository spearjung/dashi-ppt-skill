import { api } from '../lib/api'
import { krw, pct } from '../lib/format'
import { useAsync } from '../lib/useAsync'
import { Empty, ErrorNote, Loading, Money, Panel } from '../components/Common'

/**
 * EP Portfolio Dashboard(§FR-12).
 * 상단 처리 대기 카운터 → 클릭 시 해당 검증 대기열로 이동한다.
 */
export function DashboardPage({
  onSelectEngagement,
}: {
  onSelectEngagement: (engagementId: number, target: string) => void
}) {
  const { data, error, loading } = useAsync(() => api.getDashboard(), [])

  if (loading) return <Loading />
  if (error) return <ErrorNote message={error} />
  if (!data) return <Empty message="표시할 데이터가 없습니다." />

  const { counters, projects, action_required: actionRequired } = data
  const firstPending = projects.find((project) => project.open_issue_count > 0) ?? projects[0]

  const counterCards: { key: keyof typeof counters; label: string; alert: boolean }[] = [
    { key: 'unconfirmed_ocr_records', label: '미확인 OCR', alert: false },
    { key: 'read_failures', label: '판독 오류', alert: true },
    { key: 'duplicate_suspects', label: '중복 의심', alert: true },
    { key: 'wbs_attribution_review', label: 'WBS 귀속 검토', alert: true },
    { key: 'pending_uploads', label: '검증 대기 업로드', alert: false },
  ]

  return (
    <>
      <Panel
        title="처리 대기"
        hint="카운터를 누르면 해당 검증 대기열로 이동합니다"
        actions={
          <button className="primary" onClick={() => onSelectEngagement(firstPending?.engagement_id ?? 0, '/upload')}>
            화면 캡처 업로드
          </button>
        }
      >
        <div className="counters">
          {counterCards.map((card) => {
            const value = counters[card.key]
            return (
              <button
                key={card.key}
                className={`counter${card.alert && value > 0 ? ' alert' : ''}`}
                onClick={() => onSelectEngagement(firstPending?.engagement_id ?? 0, '/upload')}
              >
                <b>{value}</b>
                <span>{card.label}</span>
              </button>
            )
          })}
        </div>
        <p className="small muted" style={{ marginBottom: 0 }}>
          최신 Snapshot 기준일: {data.latest_snapshot_as_of ?? '없음'}
        </p>
      </Panel>

      <Panel title="프로젝트별 최종 예상손익" hint="단위: 원(KRW)">
        {projects.length === 0 ? (
          <Empty message="등록된 프로젝트가 없습니다. 프로젝트 마스터에서 먼저 생성하십시오." />
        ) : (
          <table>
            <thead>
              <tr>
                <th>프로젝트</th>
                <th>고객사</th>
                <th>EP</th>
                <th className="n">계약금액</th>
                <th className="n">누적 실적</th>
                <th className="n">잔여투입</th>
                <th className="n">종료예상액</th>
                <th className="n">최종 예상손익</th>
                <th className="n">손익률</th>
                <th className="n">LTD 필요액</th>
                <th className="n">미청구</th>
                <th>Snapshot</th>
                <th className="n">이슈</th>
              </tr>
            </thead>
            <tbody>
              {projects.map((project) => (
                <tr key={project.engagement_id}>
                  <td>
                    <button
                      className="tiny"
                      onClick={() => onSelectEngagement(project.engagement_id, '/pnl')}
                      title="프로젝트 손익 화면으로 이동"
                    >
                      {project.engagement_code}
                    </button>
                    <span className="small muted"> {project.name}</span>
                  </td>
                  <td>{project.client}</td>
                  <td>{project.ep ?? '-'}</td>
                  <td className="n">{krw(project.total_contract_amount)}</td>
                  <td className="n">{krw(project.cumulative_usage)}</td>
                  <td className="n">
                    {project.backlog_entered ? (
                      krw(project.remaining_input_estimate)
                    ) : (
                      <span className="badge medium">미입력</span>
                    )}
                  </td>
                  <td className="n">
                    {krw(project.eac)}
                    {project.provisional && <span className="small muted"> 잠정</span>}
                  </td>
                  <td className="n">
                    <Money value={project.final_expected_balance} />
                  </td>
                  <td className="n">{pct(project.expected_margin_rate)}</td>
                  <td className="n">{krw(project.ltd_required)}</td>
                  <td className="n">{krw(project.unbilled_amount)}</td>
                  <td className="small">{project.latest_snapshot_as_of ?? '-'}</td>
                  <td className="n">
                    {project.open_issue_count > 0 ? (
                      <span className="badge low">{project.open_issue_count}</span>
                    ) : (
                      <span className="muted">0</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>

      <Panel title="조치 필요 프로젝트">
        {actionRequired.length === 0 ? (
          <Empty message="조치가 필요한 프로젝트가 없습니다." />
        ) : (
          <table>
            <thead>
              <tr>
                <th style={{ width: 140 }}>프로젝트</th>
                <th style={{ width: 80 }}>심각도</th>
                <th>조치 사유</th>
                <th style={{ width: 90 }} />
              </tr>
            </thead>
            <tbody>
              {actionRequired.map((item) => (
                <tr key={item.engagement_id}>
                  <td>{item.name}</td>
                  <td>
                    <span className={`badge ${item.severity === 'high' ? 'low' : 'medium'}`}>
                      {item.severity === 'high' ? '높음' : '보통'}
                    </span>
                  </td>
                  <td>
                    <ul style={{ margin: 0, paddingLeft: 18 }}>
                      {item.reasons.map((reason, index) => (
                        <li key={index} className="small">
                          {reason}
                        </li>
                      ))}
                    </ul>
                  </td>
                  <td>
                    <button className="tiny" onClick={() => onSelectEngagement(item.engagement_id, '/pnl')}>
                      손익 보기
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>
    </>
  )
}
