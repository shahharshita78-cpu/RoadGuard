import { useState } from 'react'
import Dashboard          from './pages/Dashboard'
import Detection          from './pages/Detection'
import History            from './pages/History'
import RoadMap            from './pages/RoadMap'
import Maintenance        from './pages/Maintenance'
import VideoInspection    from './pages/VideoInspection'
import PredictiveAnalytics from './pages/PredictiveAnalytics'
import MaintenanceOptimizer from './pages/MaintenanceOptimizer'

type Page = 'dashboard' | 'detection' | 'video' | 'map' | 'history' | 'predictions' | 'maintenance' | 'optimizer'

const PAGES: { id: Page; label: string; number: string }[] = [
  { id: 'dashboard',   label: 'Dashboard',        number: '01' },
  { id: 'detection',   label: 'Image Inspection', number: '02' },
  { id: 'video',       label: 'Video Inspection', number: '03' },
  { id: 'map',         label: 'Road Map',         number: '04' },
  { id: 'history',     label: 'History',          number: '05' },
  { id: 'predictions', label: 'Predictive Risk',  number: '06' },
  { id: 'maintenance', label: 'Maintenance',      number: '07' },
  { id: 'optimizer',   label: 'Budget Optimizer', number: '08' },
]

export default function App() {
  const [active, setActive] = useState<Page>('dashboard')

  return (
    <div className="layout">
      <nav className="sidebar">
        <div className="sidebar-logo">
          <h1>RoadGuard</h1>
          <p>Road Condition Monitoring</p>
        </div>
        {PAGES.map(p => (
          <button
            key={p.id}
            className={`nav-item ${active === p.id ? 'active' : ''}`}
            onClick={() => setActive(p.id)}
            aria-label={p.label}
            id={`nav-${p.id}`}
          >
            <span className="nav-icon">{p.number}</span>
            <span>{p.label}</span>
          </button>
        ))}

        <div style={{ marginTop: 'auto', padding: '16px 24px', borderTop: '1px solid var(--bg-dark-secondary)' }}>
          <div style={{ fontSize: '0.7rem', color: 'var(--text-dark-secondary)', lineHeight: 1.8 }}>
            <div>SYSTEM ENGINE STATE: ACTIVE</div>
            <div>MODEL VER: YOLOv8-SURVEY</div>
            <div style={{ color: 'var(--text-dark-secondary)', marginTop: 2 }}>v1.2.0</div>
          </div>
        </div>
      </nav>

      <main className="main-content" id="main-content">
        {active === 'dashboard'   && <Dashboard />}
        {active === 'detection'   && <Detection />}
        {active === 'video'       && <VideoInspection />}
        {active === 'map'         && <RoadMap />}
        {active === 'history'     && <History />}
        {active === 'predictions' && <PredictiveAnalytics />}
        {active === 'maintenance' && <Maintenance />}
        {active === 'optimizer'   && <MaintenanceOptimizer />}
      </main>
    </div>
  )
}
