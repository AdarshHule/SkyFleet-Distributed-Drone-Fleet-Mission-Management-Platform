import { useCallback, useEffect, useRef, useState } from 'react'
import { applyPoll, getCommand, isTerminal, sendCommand, type CommandType, type TrackedCommand } from './commands'

const SITE_ID = 'PUNE-001' // known shortcut: the Fleet service will provide this
const POLL_MS = 1000

export function useCommand(droneId: string | undefined) {
  const [current, setCurrent] = useState<TrackedCommand | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const inFlight = useRef(false) // changes instantly, unlike state: blocks double-clicks

  const send = useCallback(
    async (type: CommandType, target?: { latitude: number; longitude: number }) => {
      if (!droneId || inFlight.current) return
      inFlight.current = true
      setBusy(true)
      setError(null)
      const key = crypto.randomUUID() // one key per click (per intent)
      try {
        const body = { drone_id: droneId, site_id: SITE_ID, type, ...(target ? { target } : {}) }
        setCurrent(await sendCommand(body, key))
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e))
      } finally {
        inFlight.current = false
        setBusy(false)
      }
    },
    [droneId],
  )

  useEffect(() => {
    if (!current || isTerminal(current.state)) return
    let cancelled = false
    const timer = window.setTimeout(async () => {
      try {
        const fresh = await getCommand(current.command_id)
        if (!cancelled) setCurrent((c) => applyPoll(c, fresh))
      } catch {
        if (!cancelled) setCurrent((c) => (c ? { ...c } : c)) // new object -> poll again
      }
    }, POLL_MS)
    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [current])

  return { current, busy, error, send }
}