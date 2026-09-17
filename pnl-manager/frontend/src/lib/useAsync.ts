import { useCallback, useEffect, useState } from 'react'

/** 비동기 조회 훅. reload로 재조회한다. */
export function useAsync<T>(loader: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [tick, setTick] = useState(0)

  const run = useCallback(loader, deps)

  useEffect(() => {
    let alive = true
    setLoading(true)
    run()
      .then((value) => {
        if (alive) {
          setData(value)
          setError(null)
        }
      })
      .catch((err: unknown) => {
        if (alive) setError(err instanceof Error ? err.message : String(err))
      })
      .finally(() => {
        if (alive) setLoading(false)
      })
    return () => {
      alive = false
    }
  }, [run, tick])

  return { data, error, loading, reload: () => setTick((t) => t + 1), setData }
}
