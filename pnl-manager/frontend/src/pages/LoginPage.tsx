import { useState } from 'react'

import { api } from '../lib/api'

/**
 * 로그인 화면(공용 비밀번호).
 *
 * 비밀번호는 하나이므로 이름을 함께 입력받는다. 입력한 이름이 확정·수정 기록의
 * 행위자로 남아 감사 추적이 유지된다(§9).
 */
export function LoginPage({ onLoggedIn }: { onLoggedIn: (name: string | null) => void }) {
  const [name, setName] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const result = await api.login(name, password)
      onLoggedIn(result.name)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="login-shell">
      <form className="login-card" onSubmit={submit}>
        <h1>프로젝트 손익관리</h1>
        <p className="small muted">
          담당 프로젝트의 손익과 필요 조치를 확인합니다. 입력한 이름은 확정·수정 기록의
          행위자로 남습니다.
        </p>
        {error && <div className="alert error">{error}</div>}
        <label className="field">
          이름
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="확정 기록에 남길 이름"
            autoComplete="name"
            required
          />
        </label>
        <label className="field">
          비밀번호
          <input
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete="current-password"
            required
          />
        </label>
        <button className="primary" type="submit" disabled={busy || !name || !password}>
          {busy ? '확인 중…' : '로그인'}
        </button>
      </form>
    </div>
  )
}
