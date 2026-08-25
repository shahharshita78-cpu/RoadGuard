import { useEffect, useState } from 'react'
import { MapContainer, TileLayer, CircleMarker, Popup } from 'react-leaflet'
import apiService, { InspectionRecord } from '../services/api'

const SEVERITY_COLORS: Record<string, string> = {
  High: '#f87171', Medium: '#fbbf24', Low: '#34d399',
}

export default function RoadMap() {
  const [records, setRecords] = useState<InspectionRecord[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    apiService.listInspections()
      .then(data => setRecords(data.filter(r => r.latitude && r.longitude)))
      .finally(() => setLoading(false))
  }, [])

  const withCoords = records.filter(r => r.latitude && r.longitude)

  const center: [number, number] = withCoords.length > 0
    ? [withCoords[withCoords.length - 1].latitude!, withCoords[withCoords.length - 1].longitude!]
    : [20.5937, 78.9629]  // Default: India

  if (loading) return <div className="loading"><div className="spinner" /><span>Loading map…</span></div>

  return (
    <div>
      <div className="page-header">
        <h2>Road Damage Map</h2>
        <p>GPS-mapped locations of all recorded road damage inspections. Colour indicates severity.</p>
      </div>

      <div style={{ display: 'flex', gap: 12, marginBottom: 16, flexWrap: 'wrap' }}>
        {Object.entries(SEVERITY_COLORS).map(([sev, color]) => (
          <div key={sev} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
            <div style={{ width: 12, height: 12, borderRadius: '50%', background: color }} />
            {sev}
          </div>
        ))}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.8rem', color: 'var(--text-secondary)', marginLeft: 'auto' }}>
          {withCoords.length} location{withCoords.length !== 1 ? 's' : ''} plotted
        </div>
      </div>

      <div className="map-container">
        <MapContainer center={center} zoom={withCoords.length > 0 ? 13 : 5}
          style={{ height: '100%', width: '100%', background: '#0a0e1a' }}>
          <TileLayer
            url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
            attribution='&copy; <a href="https://carto.com/">CARTO</a>'
          />
          {withCoords.map(r => (
            <CircleMarker
              key={r.inspection_id}
              center={[r.latitude!, r.longitude!]}
              radius={10}
              pathOptions={{
                color: SEVERITY_COLORS[r.severity] || '#fbbf24',
                fillColor: SEVERITY_COLORS[r.severity] || '#fbbf24',
                fillOpacity: 0.7,
                weight: 2,
              }}
            >
              <Popup>
                <div style={{ minWidth: 200, fontFamily: 'Inter, sans-serif', fontSize: 13 }}>
                  <strong style={{ display: 'block', marginBottom: 6 }}>{r.image_name}</strong>
                  {r.address && <div style={{ marginBottom: 8, color: '#64748b', fontSize: 11 }}>{r.address}</div>}
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                    <tbody>
                      {[
                        ['Severity', `${r.severity} (${r.severity_score})`],
                        ['Road Health', `${r.road_condition} (${r.road_health_score})`],
                        ['Priority', r.priority],
                        ['Detections', r.detection_count],
                        ['Date', new Date(r.timestamp).toLocaleDateString()],
                      ].map(([k, v]) => (
                        <tr key={k as string}>
                          <td style={{ padding: '3px 6px 3px 0', color: '#64748b' }}>{k}</td>
                          <td style={{ padding: '3px 0', fontWeight: 600 }}>{v}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Popup>
            </CircleMarker>
          ))}
        </MapContainer>
      </div>

      {withCoords.length === 0 && (
        <div className="card" style={{ marginTop: 16 }}>
          <div className="empty-state">
            <h3>No geolocated inspections yet.</h3>
            <p>Upload images with GPS EXIF metadata, or enter coordinates manually on the Detection page.</p>
          </div>
        </div>
      )}
    </div>
  )
}
