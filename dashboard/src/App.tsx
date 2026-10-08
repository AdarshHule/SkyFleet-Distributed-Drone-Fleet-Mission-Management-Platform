import { useEffect, useState } from 'react'
import { CircleMarker, MapContainer, TileLayer, Tooltip } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import './App.css'
import { isStale } from './drones'
import { useLiveDrones } from './useLiveDrones'

const PUNE: [number, number] = [18.5204, 73.8567]

export default function App() {
  const { fleet, link } = useLiveDrones()
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(id)
  }, [])

  const drones = Object.values(fleet).sort((a, b) => a.drone_id.localeCompare(b.drone_id))

  return (
    <div className="layout">
      <MapContainer center={PUNE} zoom={15} className="map">
        <TileLayer
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        />
        {drones.map((d) => (
          <CircleMarker
            key={d.drone_id}
            center={[d.latitude, d.longitude]}
            radius={9}
            pathOptions={{ color: isStale(d, now) ? '#888' : '#0a7', fillOpacity: 0.8 }}
          >
            <Tooltip>{d.drone_id}</Tooltip>
          </CircleMarker>
        ))}
      </MapContainer>

      <aside className="panel">
        <h1>SkyFleet</h1>
        <p className={`link link-${link}`}>Live link: {link}</p>
        {drones.length === 0 && <p>No drones yet.</p>}
        {drones.map((d) => {
          const stale = isStale(d, now)
          const ageS = Math.max(0, Math.round((now - Date.parse(d.occurred_at)) / 1000))
          return (
            <div key={d.drone_id} className={`card ${stale ? 'stale' : ''}`}>
              <strong>{d.drone_id}</strong>
              <div>Status: {stale ? 'NO SIGNAL' : d.status}</div>
              <div>Battery: {d.battery_pct}%</div>
              <div>
                Altitude: {d.altitude_m.toFixed(0)} m · Speed: {d.speed_mps.toFixed(1)} m/s
              </div>
              <div>Last seen: {ageS} s ago</div>
            </div>
          )
        })}
      </aside>
    </div>
  )
}