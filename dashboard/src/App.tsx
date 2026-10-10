import { useEffect, useState } from 'react'
import { CircleMarker, MapContainer, TileLayer, Tooltip, useMapEvents } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import './App.css'
import { isStale } from './drones'
import { useCommand } from './useCommand'
import { useLiveDrones } from './useLiveDrones'

const PUNE: [number, number] = [18.5204, 73.8567]

function ClickToGoto({ onPick }: { onPick: (lat: number, lon: number) => void }) {
  useMapEvents({ click: (e) => onPick(e.latlng.lat, e.latlng.lng) })
  return null
}

export default function App() {
  const { fleet, link } = useLiveDrones()
  const [now, setNow] = useState(() => Date.now())
  const [selectedId, setSelectedId] = useState<string | null>(null)

  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(id)
  }, [])

  const drones = Object.values(fleet).sort((a, b) => a.drone_id.localeCompare(b.drone_id))
  const selected = selectedId ?? drones[0]?.drone_id
  const { current, busy, error, send } = useCommand(selected)

  return (
    <div className="layout">
      <MapContainer center={PUNE} zoom={15} className="map">
        <TileLayer
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        />
        <ClickToGoto onPick={(lat, lon) => send('GOTO', { latitude: lat, longitude: lon })} />
        {drones.map((d) => (
          <CircleMarker
            key={d.drone_id}
            center={[d.latitude, d.longitude]}
            radius={d.drone_id === selected ? 11 : 9}
            pathOptions={{ color: isStale(d, now) ? '#888' : '#0a7', fillOpacity: 0.8 }}
            eventHandlers={{ click: () => setSelectedId(d.drone_id) }}
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
            <div
              key={d.drone_id}
              className={`card ${stale ? 'stale' : ''} ${d.drone_id === selected ? 'selected' : ''}`}
              onClick={() => setSelectedId(d.drone_id)}
            >
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

        {selected && (
          <section className="controls">
            <h2>Commands · {selected}</h2>
            <div className="buttons">
              <button disabled={busy} onClick={() => send('LAND')}>Land</button>
              <button disabled={busy} onClick={() => send('RETURN_HOME')}>Return home</button>
            </div>
            <p className="hint">Click the map to send the drone there.</p>
            {current && (
              <p className={`badge badge-${current.state.toLowerCase()}`}>
                {current.type} · {current.state}
                {current.reason ? ` · ${current.reason}` : ''}
              </p>
            )}
            {error && <p className="error">{error}</p>}
          </section>
        )}
      </aside>
    </div>
  )
}