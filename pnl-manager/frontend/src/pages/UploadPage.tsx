import { useRef, useState } from 'react'
import { Link } from 'react-router-dom'

import { Empty, ErrorNote, Loading, Panel } from '../components/Common'
import { QualityGuide } from '../components/QualityGuide'
import { api } from '../lib/api'
import { SCREEN_LABELS } from '../lib/format'
import { useAsync } from '../lib/useAsync'
import type { ScreenType, Upload } from '../types'

const STATUS_LABELS: Record<string, string> = {
  uploaded: '업로드됨',
  ocr_done: '판독 완료',
  verifying: '검증 중',
  confirmed: '확정',
  excluded: '제외',
}

/** 캡처 업로드 화면(§FR-02, §FR-03). */
export function UploadPage({ engagementId }: { engagementId: number | null }) {
  const [screenType, setScreenType] = useState<ScreenType | ''>('')
  const [actor, setActor] = useState('')
  const [dragOver, setDragOver] = useState(false)
  const [busy, setBusy] = useState(false)
  const [messages, setMessages] = useState<{ text: string; kind: 'ok' | 'warn' | 'error' }[]>([])
  const fileInput = useRef<HTMLInputElement>(null)

  const uploads = useAsync(
    () => (engagementId ? api.listUploads(engagementId) : Promise.resolve([] as Upload[])),
    [engagementId],
  )

  if (!engagementId) return <Empty message="상단에서 프로젝트를 선택하십시오." />

  async function handleFiles(files: File[]) {
    if (files.length === 0) return
    setBusy(true)
    setMessages([])
    const notes: { text: string; kind: 'ok' | 'warn' | 'error' }[] = []
    try {
      const results = await api.uploadCaptures(
        engagementId!,
        files,
        screenType || undefined,
        actor || undefined,
      )
      for (const result of results) {
        if (result.duplicate) {
          // §12.2-7 동일 해시 재업로드는 경고하고 자동 확정하지 않는다
          notes.push({
            text: result.message ?? `중복 캡처입니다 (Upload #${result.upload.id}).`,
            kind: 'warn',
          })
          continue
        }
        try {
          const upload = await api.runOcr(result.upload.id)
          notes.push({
            text:
              `Upload #${upload.id} 판독 완료 — 화면 유형 ${SCREEN_LABELS[upload.screen_type] ?? upload.screen_type}` +
              `(${upload.screen_type_source === 'user' ? '사용자 지정' : '자동 분류'})`,
            kind: 'ok',
          })
          for (const warning of upload.warnings ?? []) {
            notes.push({ text: `Upload #${upload.id}: ${warning}`, kind: 'warn' })
          }
        } catch (error) {
          notes.push({
            text:
              `Upload #${result.upload.id} 판독 실패: ` +
              (error instanceof Error ? error.message : String(error)) +
              ' — 검증 화면에서 값을 직접 입력할 수 있습니다.',
            kind: 'error',
          })
        }
      }
    } catch (error) {
      notes.push({ text: error instanceof Error ? error.message : String(error), kind: 'error' })
    } finally {
      setBusy(false)
      setMessages(notes)
      uploads.reload()
    }
  }

  return (
    <>
      <Panel title="화면 캡처 업로드" hint="여러 장 동시 Drag & Drop · 클립보드 붙여넣기 지원">
        <div className="row" style={{ marginBottom: 10 }}>
          <label className="field">
            화면 유형
            <select value={screenType} onChange={(event) => setScreenType(event.target.value as ScreenType | '')}>
              <option value="">자동 분류에 위임</option>
              {Object.entries(SCREEN_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            업로더
            <input value={actor} onChange={(event) => setActor(event.target.value)} placeholder="EP 또는 EM" />
          </label>
        </div>

        <div
          className={`dropzone${dragOver ? ' over' : ''}`}
          onDragOver={(event) => {
            event.preventDefault()
            setDragOver(true)
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(event) => {
            event.preventDefault()
            setDragOver(false)
            void handleFiles(Array.from(event.dataTransfer.files))
          }}
          onPaste={(event) => {
            const pasted = Array.from(event.clipboardData.files)
            if (pasted.length > 0) void handleFiles(pasted)
          }}
          onClick={() => fileInput.current?.click()}
          tabIndex={0}
          role="button"
        >
          {busy ? '업로드·판독 중…' : '캡처 이미지를 끌어다 놓거나 클릭해 선택하십시오 (PNG·JPG·WEBP)'}
          <input
            ref={fileInput}
            type="file"
            multiple
            accept="image/png,image/jpeg,image/webp"
            style={{ display: 'none' }}
            onChange={(event) => {
              void handleFiles(Array.from(event.target.files ?? []))
              event.target.value = ''
            }}
          />
        </div>

        {messages.map((message, index) => (
          <div
            key={index}
            className={`alert${message.kind === 'error' ? ' error' : message.kind === 'ok' ? ' ok' : ''}`}
          >
            {message.text}
          </div>
        ))}
      </Panel>

      <Panel title="업로드 목록" actions={<button className="tiny" onClick={uploads.reload}>새로고침</button>}>
        {uploads.loading ? (
          <Loading />
        ) : uploads.error ? (
          <ErrorNote message={uploads.error} />
        ) : (uploads.data ?? []).length === 0 ? (
          <Empty message="업로드된 캡처가 없습니다." />
        ) : (
          <table>
            <thead>
              <tr>
                <th className="n">#</th>
                <th>파일</th>
                <th>화면 유형</th>
                <th>표 제목</th>
                <th>기준일</th>
                <th>단위</th>
                <th>상태</th>
                <th>경고</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {(uploads.data ?? []).map((upload) => (
                <tr key={upload.id}>
                  <td className="n">{upload.id}</td>
                  <td className="small">{upload.original_filename ?? '-'}</td>
                  <td>
                    {SCREEN_LABELS[upload.screen_type] ?? upload.screen_type}
                    {upload.screen_type_source !== 'user' && (
                      <span className="badge medium" style={{ marginLeft: 4 }}>
                        확인 필요
                      </span>
                    )}
                  </td>
                  <td className="small">{upload.screen_title ?? '-'}</td>
                  <td className="small">{upload.as_of_date ?? '-'}</td>
                  <td className="small">{upload.unit ?? <span className="badge low">미표시</span>}</td>
                  <td>
                    <span className={`badge${upload.status === 'confirmed' ? ' high' : ''}`}>
                      {STATUS_LABELS[upload.status] ?? upload.status}
                    </span>
                  </td>
                  <td className="small">{(upload.warnings ?? []).length || ''}</td>
                  <td>
                    <Link to={`/verify/${upload.id}`}>
                      <button className="tiny">검증</button>
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>

      <QualityGuide />
    </>
  )
}
