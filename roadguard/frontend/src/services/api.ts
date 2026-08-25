import axios from 'axios'

const baseURL = import.meta.env.VITE_API_BASE_URL || '/api'
const api = axios.create({ baseURL })

export interface BoundingBox { x1: number; y1: number; x2: number; y2: number }
export interface Detection  { damage_class: string; confidence: number; bbox: BoundingBox }
export interface SeverityInfo  { severity_score: number; severity: string }
export interface RoadHealthInfo { road_health_score: number; road_condition: string }
export interface MaintenancePriorityInfo { priority_score: number; priority: string; reasons: string[] }

export interface AnalysisResult {
  detections: Detection[]
  image_width: number
  image_height: number
  detection_count: number
  severity: SeverityInfo
  road_health: RoadHealthInfo
  maintenance_priority: MaintenancePriorityInfo
  latitude: number | null
  longitude: number | null
  address: string | null
}

export interface InspectionRecord {
  id: number
  inspection_id: string
  timestamp: string
  image_name: string
  latitude: number | null
  longitude: number | null
  address: string | null
  damage_classes: string
  detection_count: number
  severity_score: number
  severity: string
  road_health_score: number
  road_condition: string
  priority_score: number
  priority: string
}

export interface AnalyticsSummary {
  total_inspections: number
  total_detections: number
  critical_inspections: number
  avg_road_health: number
  avg_severity_score: number
  class_distribution: Record<string, number>
  priority_distribution: Record<string, number>
}

export const apiService = {
  health: () => api.get('/health').then(r => r.data),

  detect: (file: File, confidence: number, manualLat?: number, manualLon?: number) => {
    const form = new FormData()
    form.append('file', file)
    form.append('confidence', String(confidence))
    if (manualLat !== undefined) form.append('manual_lat', String(manualLat))
    if (manualLon !== undefined) form.append('manual_lon', String(manualLon))
    return api.post<AnalysisResult>('/detect', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then(r => r.data)
  },

  listInspections: () => api.get<InspectionRecord[]>('/inspections').then(r => r.data),

  getInspection: (id: string) => api.get<InspectionRecord>(`/inspections/${id}`).then(r => r.data),

  analyticsSummary: () => api.get<AnalyticsSummary>('/analytics/summary').then(r => r.data),

  maintenanceQueue: () => api.get<InspectionRecord[]>('/maintenance/queue').then(r => r.data),
}

export default apiService
