import type { DroneState } from './types'

export type Fleet = Record<string, DroneState>

/** Apply `incoming` to the fleet, but only if it is newer than what we already have. */
export function mergeDrone(fleet: Fleet, incoming: DroneState): Fleet {
  const current = fleet[incoming.drone_id]

  if (
    current !== undefined &&
    Date.parse(incoming.occurred_at) <= Date.parse(current.occurred_at)
  ) {
    return fleet
  }

  return { ...fleet, [incoming.drone_id]: incoming }
}

export const STALE_AFTER_MS = 5000

export function isStale(drone: DroneState, nowMs: number): boolean {
  return nowMs - Date.parse(drone.occurred_at) > STALE_AFTER_MS
}