import { useCallback, useEffect, useState } from 'react'
import { NavLink, Navigate, Route, Routes, useNavigate } from 'react-router-dom'

import { api, onUnauthorized } from './lib/api'
import type { Engagement } from './types'
import { DashboardPage } from './pages/DashboardPage'
import { LoginPage } from './pages/LoginPage'
import { MasterPage } from './pages/MasterPage'
import { ProjectPnlPage } from './pages/ProjectPnlPage'
import { ScenarioPage } from './pages/ScenarioPage'
import { UploadPage } from './pages/UploadPage'
import { VerifyPage } from './pages/VerifyPage'

type AuthState = 'checking' | 'anonymous' | 'authenticated'

export function App() {
  const [engagements, setEngagements] = useState<Engagement[]>([])
  const [selected, setSelected] = useState<number | null>(null)
  const [bootError, setBootError] = useState<string | null>(null)
  const [authState, setAuthState] = useState<AuthState>('checking')
  const [actor, setActor] = useState<string | null>(null)
  const navigate = useNavigate()

  const refreshEngagements = useCallback(
    () =>
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
        ),
    [],
  )

  // 세션이 끊기면(만료·로그아웃) 즉시 로그인 화면으로 돌아간다.
  useEffect(() => onUnauthorized(() => setAuthState('anonymous')), [])

  useEffect(() => {
    api
      .getSession()
      .then((session) => {
        setActor(session.name)
        setAuthState(session.authenticated ? 'authenticated' : 'anonymous')
      })
      .catch(() => {
        // 세션 확인 자체가 실패하면 백엔드 연결 문제로 본다.
        setAuthState('anonymous')
        setBootError('백엔드에 연결할 수 없습니다.')
      })
  }, [])

  useEffect(() => {
    if (authState === 'authenticated') void refreshEngagements()
  }, [authState, refreshEngagements])

  if (authState === 'checking') {
    return <p className="spinner" style={{ padding: 24 }}>확인 중…</p>
  }

  if (authState === 'anonymous') {
    return (
      <>
        {bootError && (
          <div className="login-shell">
            <div className="alert error">{bootError}</div>
          </div>
        )}
        <LoginPage
          onLoggedIn={(name) => {
            setActor(name)
            setBootError(null)
            setAuthState('authenticated')
          }}
        />
      </>
    )
  }

  const engagementId = selected

  async function logout() {
    try {
      await api.logout()
    } finally {
      setActor(null)
      setEngagements([])
      setSelected(null)
      setAuthState('anonymous')
    }
  }

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
        {actor && (
          <span className="session">
            <span className="small">{actor}</span>
            <button className="tiny ghost" onClick={logout}>
              로그아웃
            </button>
          </span>
        )}
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
