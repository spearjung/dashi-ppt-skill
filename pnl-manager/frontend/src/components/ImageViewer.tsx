import { useState } from 'react'

import { api } from '../lib/api'
import type { OcrRecord } from '../types'

/**
 * 검증 화면 좌측 원본 캡처(§7). 선택된 레코드의 추출 영역을 하이라이트한다.
 * bbox는 0~1 비율 좌표 [x, y, w, h]로 저장된다.
 */
export function ImageViewer({
  uploadId,
  records,
  highlightedId,
}: {
  uploadId: number
  records: OcrRecord[]
  highlightedId: number | null
}) {
  const [failed, setFailed] = useState(false)
  const [zoom, setZoom] = useState(1)

  const boxes = records
    .filter((record) => record.bbox && record.bbox.length === 4)
    .filter((record) => highlightedId === null || record.id === highlightedId)

  return (
    <div>
      <div className="row" style={{ marginBottom: 6 }}>
        <span className="small muted">원본 캡처</span>
        <span style={{ marginLeft: 'auto' }} className="row">
          <button className="tiny" onClick={() => setZoom((z) => Math.max(0.5, z - 0.25))}>
            축소
          </button>
          <span className="small mono">{Math.round(zoom * 100)}%</span>
          <button className="tiny" onClick={() => setZoom((z) => Math.min(3, z + 0.25))}>
            확대
          </button>
          <a href={api.imageUrl(uploadId)} target="_blank" rel="noreferrer" className="small">
            원본 열기
          </a>
        </span>
      </div>
      <div className="image-pane" style={{ maxHeight: '70vh' }}>
        {failed ? (
          <p className="image-missing">
            원본 캡처를 불러올 수 없습니다. 파일이 이동·삭제되었는지 확인하십시오.
          </p>
        ) : (
          <div style={{ position: 'relative', width: `${zoom * 100}%` }}>
            <img src={api.imageUrl(uploadId)} alt="업로드된 캡처 원본" onError={() => setFailed(true)} />
            {boxes.map((record) => {
              const [x, y, w, h] = record.bbox as [number, number, number, number]
              return (
                <span
                  key={record.id}
                  className="bbox"
                  style={{
                    left: `${x * 100}%`,
                    top: `${y * 100}%`,
                    width: `${w * 100}%`,
                    height: `${h * 100}%`,
                  }}
                />
              )
            })}
          </div>
        )}
      </div>
      {boxes.length === 0 && !failed && (
        <p className="small muted" style={{ marginTop: 6 }}>
          판독기가 추출 영역(bbox)을 제공하지 않아 하이라이트를 표시할 수 없습니다.
        </p>
      )}
    </div>
  )
}
