import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { Empty, ErrorNote, Loading, Panel, WarningList } from '../components/Common'
import { EditableTable } from '../components/EditableTable'
import { ImageViewer } from '../components/ImageViewer'
import { SnapshotDiffView } from '../components/SnapshotDiff'
import { api } from '../lib/api'
import { ITEM_LABELS, SCREEN_LABELS, krw, signed } from '../lib/format'
import { useAsync } from '../lib/useAsync'
import type { Decision, ItemType, SnapshotDiff, VerificationView } from '../types'

/** OCR 검증 화면(§7). 좌 원본 캡처, 우 판독 표, 하단 산술검증·Snapshot 비교. */
export function VerifyPage() {
  const { uploadId } = useParams<{ uploadId: string }>()
  const id = Number(uploadId)
  const navigate = useNavigate()

  const [busy, setBusy] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const [hovered, setHovered] = useState<number | null>(null)
  const [confirmResult, setConfirmResult] = useState<{ snapshotId: number | null; diff: SnapshotDiff | null } | null>(
    null,
  )

  const view = useAsync(() => api.getVerification(id), [id])
  const wbs = useAsync(
    () =>
      view.data
        ? api.listWbs(view.data.upload.engagement_id)
        : Promise.resolve([]),
    [view.data?.upload.engagement_id],
  )

  if (view.loading) return <Loading />
  if (view.error) return <ErrorNote message={view.error} />
  if (!view.data) return <Empty message="업로드를 찾을 수 없습니다." />

  const { upload, records, confirmed, arithmetic_log: checks, snapshot_comparison: comparison, gate } = view.data

  async function run(task: () => Promise<VerificationView>) {
    setBusy(true)
    setActionError(null)
    try {
      view.setData(await task())
    } catch (error) {
      setActionError(error instanceof Error ? error.message : String(error))
    } finally {
      setBusy(false)
    }
  }

  const applyDecisions = (decisions: Decision[]) =>
    run(() => api.applyDecisions(id, decisions, 'EP'))

  async function confirmUpload() {
    setBusy(true)
    setActionError(null)
    try {
      const result = await api.confirmUpload(id, 'EP')
      setConfirmResult({ snapshotId: result.snapshot_id, diff: result.diff })
      view.reload()
    } catch (error) {
      setActionError(error instanceof Error ? error.message : String(error))
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <Panel
        title={`Upload #${upload.id} 검증`}
        hint={`${SCREEN_LABELS[upload.screen_type] ?? upload.screen_type} · ${upload.screen_title ?? '표 제목 없음'} · 기준일 ${upload.as_of_date ?? '-'} · 단위 ${upload.unit ?? '미표시'} · 판독엔진 ${upload.ocr_provider ?? '-'}`}
        actions={
          <span className="row">
            <Link to="/upload">
              <button className="tiny">업로드 목록</button>
            </Link>
            <button
              className="primary"
              disabled={busy || !gate.can_confirm || upload.status === 'confirmed'}
              onClick={confirmUpload}
              title={gate.can_confirm ? '확정 후 Snapshot을 생성합니다' : gate.blockers.join(' / ')}
            >
              {upload.status === 'confirmed' ? '확정 완료' : '최종 확정'}
            </button>
          </span>
        }
      >
        {actionError && <ErrorNote message={actionError} />}
        {upload.screen_type_source !== 'user' && (
          <div className="alert">
            화면 유형이 자동 분류되었습니다({SCREEN_LABELS[upload.screen_type]}). 확인하거나 변경하십시오.
            <div className="row" style={{ marginTop: 6 }}>
              <select
                defaultValue={upload.screen_type}
                onChange={(event) => {
                  void api.setScreenType(id, event.target.value).then(() => view.reload())
                }}
              >
                {Object.entries(SCREEN_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
              <span className="small muted">선택 즉시 사용자 확정으로 기록됩니다.</span>
            </div>
          </div>
        )}
        <WarningList title="캡처·판독 경고" items={upload.warnings ?? []} />
        {gate.can_confirm ? (
          <div className="alert ok">확정 조건을 충족했습니다. 최종 확정 시 Snapshot이 생성됩니다.</div>
        ) : (
          <WarningList title="확정 차단 사유" items={gate.blockers} />
        )}
        {confirmResult && (
          <div className="alert ok">
            확정 완료 — Snapshot #{confirmResult.snapshotId ?? '-'} 생성.{' '}
            <button
              className="tiny"
              onClick={() => navigate('/pnl')}
            >
              프로젝트 손익 보기
            </button>
          </div>
        )}
      </Panel>

      <div className="grid verify">
        <section className="panel">
          <ImageViewer uploadId={id} records={records} highlightedId={hovered} />
        </section>
        <section className="panel">
          <h2>
            판독 결과 <span className="hint">{records.length}개 필드 · 값별 액션 6종</span>
          </h2>
          {records.length === 0 ? (
            <Empty message="추출된 행이 없습니다. 아래에서 값을 직접 입력하십시오." />
          ) : (
            <EditableTable
              records={records}
              confirmed={confirmed}
              wbsList={wbs.data ?? []}
              onApply={applyDecisions}
              onHover={setHovered}
              busy={busy}
            />
          )}
        </section>
      </div>

      <ManualEntry
        uploadId={id}
        wbsOptions={(wbs.data ?? []).map((row) => ({ id: row.id, code: row.code }))}
        onAdded={(next) => view.setData(next)}
      />

      <Panel title="산술 교차검증" hint="Time + Expense + OS = 화면 합계 / Time + Expense − Billing = WIP">
        {checks.length === 0 ? (
          <Empty message="검증할 합계 정보가 화면에 없습니다." />
        ) : (
          <table>
            <thead>
              <tr>
                <th>규칙</th>
                <th className="n">행</th>
                <th className="n">산식 결과</th>
                <th className="n">화면 표시값</th>
                <th className="n">차이</th>
                <th>결과</th>
                <th>비고</th>
              </tr>
            </thead>
            <tbody>
              {checks.map((check, index) => (
                <tr key={index}>
                  <td className="mono">{check.rule}</td>
                  <td className="n">{check.row_index ?? '전체'}</td>
                  <td className="n">{krw(check.actual)}</td>
                  <td className="n">{krw(check.expected)}</td>
                  <td className="n">{signed(check.diff)}</td>
                  <td>
                    <span className={`badge ${check.passed ? 'high' : 'low'}`}>
                      {check.passed ? '통과' : '불일치'}
                    </span>
                  </td>
                  <td className="small">{check.message ?? ''}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>

      {comparison && (
        <Panel title="이전 Snapshot 비교" hint={`Snapshot #${comparison.snapshot_id} · 기준일 ${comparison.as_of_date ?? '-'}`}>
          <table className="diff-table">
            <thead>
              <tr>
                <th>WBS · 항목</th>
                <th className="n">Snapshot 값</th>
                <th className="n">판독값</th>
                <th className="n">차이</th>
              </tr>
            </thead>
            <tbody>
              {comparison.rows.map((row) => (
                <tr key={row.ocr_record_id}>
                  <td className="small mono">{row.key}</td>
                  <td className="n">{krw(row.snapshot_amount)}</td>
                  <td className="n">{krw(row.ocr_amount)}</td>
                  <td className={`n ${(row.delta ?? 0) > 0 ? 'delta-pos' : (row.delta ?? 0) < 0 ? 'delta-neg' : ''}`}>
                    {signed(row.delta)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
      )}

      {confirmResult?.diff && <SnapshotDiffView diff={confirmResult.diff} title="확정 전·후 Snapshot 증감" />}
    </>
  )
}

/** 판독 실패·미판독 값 직접 입력(§FR-04 Failed, §9 오프라인 가용성). */
function ManualEntry({
  uploadId,
  wbsOptions,
  onAdded,
}: {
  uploadId: number
  wbsOptions: { id: number; code: string }[]
  onAdded: (view: VerificationView) => void
}) {
  const [itemType, setItemType] = useState<ItemType>('time')
  const [wbsId, setWbsId] = useState<number | ''>('')
  const [amount, setAmount] = useState('')
  const [quantity, setQuantity] = useState('')
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const isQuantity = itemType === 'backlog_mm'

  async function submit() {
    setBusy(true)
    setError(null)
    try {
      const next = await api.addManualRecord(uploadId, {
        item_type: itemType,
        wbs_id: wbsId === '' ? null : wbsId,
        amount: isQuantity ? null : Number(amount.replace(/,/g, '')) || null,
        quantity: isQuantity ? Number(quantity) || null : null,
        period_from: from || null,
        period_to: to || null,
        raw_label: '직접 입력',
        actor: 'EP',
      })
      onAdded(next)
      setAmount('')
      setQuantity('')
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Panel title="값 직접 입력" hint="판독 실패 필드·오프라인 환경에서 사용합니다">
      {error && <ErrorNote message={error} />}
      <div className="row">
        <label className="field">
          항목
          <select value={itemType} onChange={(event) => setItemType(event.target.value as ItemType)}>
            {Object.entries(ITEM_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          WBS
          <select value={wbsId} onChange={(event) => setWbsId(event.target.value ? Number(event.target.value) : '')}>
            <option value="">선택</option>
            {wbsOptions.map((option) => (
              <option key={option.id} value={option.id}>
                {option.code}
              </option>
            ))}
          </select>
        </label>
        {isQuantity ? (
          <label className="field">
            수량(MM)
            <input className="n" value={quantity} onChange={(event) => setQuantity(event.target.value)} />
          </label>
        ) : (
          <label className="field">
            금액(원)
            <input className="n" value={amount} onChange={(event) => setAmount(event.target.value)} />
          </label>
        )}
        <label className="field">
          조회 시작일
          <input type="date" value={from} onChange={(event) => setFrom(event.target.value)} />
        </label>
        <label className="field">
          조회 종료일
          <input type="date" value={to} onChange={(event) => setTo(event.target.value)} />
        </label>
        <button disabled={busy} onClick={submit} style={{ alignSelf: 'flex-end' }}>
          추가
        </button>
      </div>
    </Panel>
  )
}
