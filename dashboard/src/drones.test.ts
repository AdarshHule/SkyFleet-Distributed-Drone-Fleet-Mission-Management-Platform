import { describe, expect, it } from 'vitest'
import { isStale, mergeDrone, type Fleet } from './drones'
import type { DroneState } from './types'

const base: DroneState = {
  drone_id: 'SF-PN-001', occurred_at: '2026-10-07T10:00:05Z',
  latitude: 18.52, longitude: 73.85, altitude_m: 80, speed_mps: 10,
  battery_pct: 89, gps_satellites: 14, heading_deg: 0, status: 'FLYING',
}
const at = (occurred_at: string, battery_pct: number): DroneState =>
  ({ ...base, occurred_at, battery_pct })

describe('mergeDrone', () => {
  it('adds a new drone', () => {
    expect(mergeDrone({}, base)['SF-PN-001'].battery_pct).toBe(89)
  })

  it('ignores a late message and returns the same object', () => {
    const fleet: Fleet = { 'SF-PN-001': base }
    expect(mergeDrone(fleet, at('2026-10-07T10:00:02Z', 91))).toBe(fleet)
  })

  it('applies a newer message', () => {
    const fleet: Fleet = { 'SF-PN-001': base }
    expect(mergeDrone(fleet, at('2026-10-07T10:00:08Z', 88))['SF-PN-001'].battery_pct).toBe(88)
  })

  it('compares instants, not strings', () => {
    // 15:30:05 IST is 10:00:05 UTC. As text, "10:00:06Z" looks smaller than "15:30:05",
    // but as a moment in time it is one second NEWER.
    const fleet: Fleet = { 'SF-PN-001': at('2026-10-07T15:30:05+05:30', 89) }
    expect(mergeDrone(fleet, at('2026-10-07T10:00:06Z', 88))['SF-PN-001'].battery_pct).toBe(88)
  })
})

describe('isStale', () => {
  it('is fresh within 5 seconds and stale after', () => {
    const t = Date.parse(base.occurred_at)
    expect(isStale(base, t + 4000)).toBe(false)
    expect(isStale(base, t + 6000)).toBe(true)
  })
})