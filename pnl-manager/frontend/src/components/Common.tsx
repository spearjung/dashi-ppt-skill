import type { ReactNode } from 'react'

export function Panel({
  title,
  hint,
  actions,
  children,
}: {
  title?: string
  hint?: string
  actions?: ReactNode
  children: ReactNode
}) {
  return (
    <section className="panel">
      {title && (
        <h2>
          {title}
          {hint && <span className="hint">{hint}</span>}
          {actions && <span style={{ marginLeft: 'auto' }}>{actions}</span>}
        </h2>
      )}
      {children}
    </section>
  )
}

export function Loading({ label = '불러오는 중…' }: { label?: string }) {
  return <p className="spinner">{label}</p>
}

export function ErrorNote({ message }: { message: string }) {
  return <div className="alert error">{message}</div>
}

export function Empty({ message }: { message: string }) {
  return <p className="empty">{message}</p>
}

export function WarningList({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) return null
  return (
    <div className="alert">
      <strong>{title}</strong>
      <ul>
        {items.map((item, index) => (
          <li key={index}>{item}</li>
        ))}
      </ul>
    </div>
  )
}

/** 금액 셀. 음수는 손실로 강조한다. */
export function Money({ value, highlightNegative = true }: { value: number | null; highlightNegative?: boolean }) {
  const negative = highlightNegative && value !== null && value < 0
  return <span className={negative ? 'neg' : undefined}>{value === null ? '-' : value.toLocaleString('ko-KR')}</span>
}
