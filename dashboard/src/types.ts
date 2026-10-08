export type DroneStatus = 'IDLE' | 'FLYING' | 'RETURNING' | 'LANDED' | 'CHARGING'

export interface DroneState {
  drone_id: string
  occurred_at: string
  latitude: number
  longitude: number
  altitude_m: number
  speed_mps: number
  battery_pct: number
  gps_satellites: number
  heading_deg: number
  status: DroneStatus
}