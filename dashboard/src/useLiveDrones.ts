import { useEffect, useState } from 'react'
import { mergeDrone, type Fleet } from './drones'
import type { DroneState } from './types'

export type LinkStatus = 'connecting' | 'live' | 'offline'

export function useLiveDrones() {
  const [fleet, setFleet] = useState<Fleet>({})
  const [link, setLink] = useState<LinkStatus>('connecting')

  useEffect(() => {
    let ws: WebSocket | null = null
    let retry: number | undefined
    let stopped = false

    async function loadSnapshot() {
      try {
        const res = await fetch('/api/v1/drones')
        if (!res.ok) return
        const drones: DroneState[] = await res.json()
        setFleet((f) => drones.reduce(mergeDrone, f))
      } catch {
        // gateway unreachable: the WebSocket retry loop will try again
      }
    }

    function connect() {
      setLink('connecting')
      const proto = location.protocol === 'https:' ? 'wss' : 'ws'
      ws = new WebSocket(`${proto}://${location.host}/ws/telemetry`)
      ws.onopen = () => {
        setLink('live')
        loadSnapshot() // resync after every (re)connect
      }
      ws.onmessage = (event) => {
        const drone: DroneState = JSON.parse(event.data)
        setFleet((f) => mergeDrone(f, drone))
      }
      ws.onclose = () => {
        setLink('offline')
        if (!stopped) retry = window.setTimeout(connect, 2000)
      }
    }

    connect()
    return () => {
      stopped = true
      window.clearTimeout(retry)
      ws?.close()
    }
  }, [])

  return { fleet, link }
}