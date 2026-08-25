import { useState } from 'react'
import Dashboard        from './pages/Dashboard'
import Detection        from './pages/Detection'
import History          from './pages/History'
import RoadMap          from './pages/RoadMap'
import Maintenance      from './pages/Maintenance'
import VideoInspection  from './pages/VideoInspection'
import PredictiveAnalytics from './pages/PredictiveAnalytics'

type Page = 'dashboard' | 'detection' | 'history' | 'map' | 'maintenance' | 'video' | 'predictions'

const PAGES: { id: Page; label: string; icon: string }[] = [
  { id: 'dashboard',   label: 'Dashboard',        icon: '📊' },
  { id: 'detection',   label: 'Detection',        icon: '🔍' },
  { id: 'video',       label: 'Video Inspect',    icon: '🎬' },
  { id: 'predictions', label: 'Predictive Risk',  icon: '>>' },
  { id: 'history',     label: 'History',          icon: '📋' },
  { id: 'map',         label: 'Road Map',         icon: '🗺️' },
  { id: 'maintenance', label: 'Maintenance',      icon: '🔧' },
]

export default function App() {
  const [active, setActive] = useState<Page>('dashboard')

  return (
    <div className="layout">
      <nav className="sidebar">
        <div className="sidebar-logo">
          <h1>RoadGuard</h1>
          <p>Road Intelligence Platform</p>
        </div>
        {PAGES.map(p => (
          <button
            key={p.id}
            className={`nav-item ${active === p.id ? 'active' : ''}`}
            onClick={() => setActive(p.id)}
            aria-label={p.label}
            id={`nav-${p.id}`}
          >
            <span className="nav-icon">{p.icon}</span>
            <span>{p.label}</span>
          </button>
        ))}

        <div style={{ marginTop: 'auto', padding: '16px 24px', borderTop: '1px solid var(--border)' }}>
          <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', lineHeight: 1.8 }}>
            <div>YOLOv8 • FastAPI • SQLite</div>
            <div style={{ color: 'var(--text-muted)', marginTop: 2 }}>v1.1.0</div>
          </div>
        </div>
      </nav>

      <main className="main-content" id="main-content">
        {active === 'dashboard'   && <Dashboard />}
        {active === 'detection'   && <Detection />}
        {active === 'video'       && <VideoInspection />}
        {active === 'predictions' && <PredictiveAnalytics />}
        {active === 'history'     && <History />}
        {active === 'map'         && <RoadMap />}
        {active === 'maintenance' && <Maintenance />}
      </main>
    </div>
  )
}
