import { useEffect, useState } from 'react'
import { NavLink, Navigate, Route, Routes, useNavigate } from 'react-router-dom'

import { api } from './lib/api'
import type { Engagement } from './types'
import { DashboardPage } from './pages/DashboardPage'
import { MasterPage } from './pages/MasterPage'
import { ProjectPnlPage } from './pages/ProjectPnlPage'
import { ScenarioPage } from './pages/ScenarioPage'
import { UploadPage } from './pages/UploadPage'
import { VerifyPage } from './pages/VerifyPage'

export function App() {
  const [engagements, setEngagements] = useState<Engagement[]>([])
  const [selected, setSelected] = useState<number | null>(null)
  const [bootError, setBootError] = useState<string | null>(null)
  const navigate = useNavigate()

  const refreshEngagements = () =>
    api
      .listEngagements()
      .then((rows) => {
        setEngagements(rows)
        setSelected((current) => current ?? rows[0]?.id ?? null)
        setBootError(null)
      })
      .catch((error: unknown) =>
        setBootError(
          error instanceof Error
            ? `백엔드에 연결할 수 없습니다: ${error.message}`
            : '백엔드에 연결할 수 없습니다.',
        ),
      )

  useEffect(() => {
    void refreshEngagements()
  }, [])

  const engagementId = selected

  return (
    <div className="app">
      <header className="topbar">
        <h1>프로젝트 손익관리</h1>
        <select
          className="engagement-picker"
          value={engagementId ?? ''}
          onChange={(event) => setSelected(event.target.value ? Number(event.target.value) : null)}
          aria-label="프로젝트 선택"
        >
          {engagements.length === 0 && <option value="">프로젝트 없음</option>}
          {engagements.map((engagement) => (
            <option key={engagement.id} value={engagement.id}>
              {engagement.engagement_code} · {engagement.name}
            </option>
          ))}
        </select>
        <nav>
          <NavLink to="/dashboard">Dashboard</NavLink>
          <NavLink to="/upload">캡처 업로드</NavLink>
          <NavLink to="/pnl">프로젝트 손익</NavLink>
          <NavLink to="/scenario">시나리오</NavLink>
          <NavLink to="/master">프로젝트 마스터</NavLink>
        </nav>
      </header>

      <main>
        {bootError && <div className="alert error">{bootError}</div>}
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route
            path="/dashboard"
            element={
              <DashboardPage
                onSelectEngagement={(id, target) => {
                  setSelected(id)
                  navigate(target)
                }}
              />
            }
          />
          <Route path="/upload" element={<UploadPage engagementId={engagementId} />} />
          <Route path="/verify/:uploadId" element={<VerifyPage />} />
          <Route path="/pnl" element={<ProjectPnlPage engagementId={engagementId} />} />
          <Route path="/scenario" element={<ScenarioPage engagementId={engagementId} />} />
          <Route
            path="/master"
            element={<MasterPage engagementId={engagementId} onChanged={refreshEngagements} />}
          />
        </Routes>
      </main>
    </div>
  )
}
