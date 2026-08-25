import axios from 'axios'

let baseURL = import.meta.env.VITE_API_BASE_URL || '/api'
if (baseURL && !baseURL.endsWith('/api') && baseURL.startsWith('http')) {
  baseURL = `${baseURL}/api`
}
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

// ── Phase 11: Video Inspection types ────────────────────────────────────────
export interface FrameSummary {
  frame_number: number
  timestamp_sec: number
  detection_count: number
  severity_score: number
  road_health_score: number
  damage_classes: string[]
}

export interface VideoInspectionRecord {
  id?: number
  inspection_id: string
  timestamp: string
  video_name: string
  duration_seconds: number
  total_frames: number
  sampled_frames: number
  frame_interval: number
  fps: number
  total_detections: number
  unique_detections: number
  frames_with_damage: number
  damage_frame_pct: number
  avg_confidence: number
  avg_severity_score: number
  max_severity_score: number
  overall_severity: string
  road_health_score: number
  road_condition: string
  priority_score: number
  priority: string
  priority_reasons: string[]
  class_distribution: Record<string, number>
  frame_summaries: FrameSummary[]
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

  // ── Phase 11: Video Inspection ──────────────────────────────────────────
  videoDetect: (
    file: File,
    frameInterval: number = 30,
    confidence: number = 0.25,
    onUploadProgress?: (pct: number) => void,
  ) => {
    const form = new FormData()
    form.append('file', file)
    form.append('frame_interval', String(frameInterval))
    form.append('confidence', String(confidence))
    return api.post<VideoInspectionRecord>('/video/detect', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: onUploadProgress
        ? (e) => { if (e.total) onUploadProgress(Math.round((e.loaded / e.total) * 100)) }
        : undefined,
    }).then(r => r.data)
  },

  listVideoInspections: () =>
    api.get<VideoInspectionRecord[]>('/video/inspections').then(r => r.data),

  getVideoInspection: (id: string) =>
    api.get<VideoInspectionRecord>(`/video/inspections/${id}`).then(r => r.data),

  // ── Phase 12: Predictive Road Deterioration ──────────────────────────────
  getPredictiveModelMeta: () =>
    api.get<PredictiveModelMeta>('/predictions/model').then(r => r.data),

  getPredictiveRiskSummary: () =>
    api.get<PredictiveRiskSummary>('/predictions/risk-summary').then(r => r.data),

  runPredictiveInference: (payload: Record<string, any>) =>
    api.post<PredictionResult>('/predictions/deterioration', payload).then(r => r.data),

  retrainPredictiveModel: (threshold: number = 65) =>
    api.post<{ status: string; message: string; metadata: PredictiveModelMeta }>(
      `/predictions/train?high_priority_threshold=${threshold}`
    ).then(r => r.data),

  // ── Phase 13: Budget-Constrained Maintenance Optimization ─────────────────
  optimizeMaintenancePlan: (req: OptimizationRequest) =>
    api.post<OptimizationResult>('/maintenance/optimize', req).then(r => r.data),

  getLatestOptimizationPlan: () =>
    api.get<OptimizationResult>('/maintenance/optimization/latest').then(r => r.data),
}

export interface OptimizationCandidate {
  road_segment_id: string
  road_health_score: number
  severity_score: number
  priority_score: number
  detection_count: number
  avg_confidence?: number
  damage_class_counts?: Record<string, number>
  deterioration_risk?: number
  predicted_future_health?: number
}

export interface SelectedMaintenanceSegment {
  segment_id: string
  estimated_cost: number
  benefit_score: number
  current_health: number
  predicted_future_health: number
  deterioration_risk: number
  maintenance_priority: number
  reasons: string[]
}

export interface OptimizationRequest {
  budget: number
  road_segments?: OptimizationCandidate[]
}

export interface OptimizationResult {
  id?: number
  optimization_id: string
  timestamp: string
  status: string
  budget: number
  allocated_budget: number
  remaining_budget: number
  total_expected_benefit: number
  estimated_health_improvement: number
  estimated_risk_reduction: number
  selected_count: number
  candidate_count: number
  selected_segments: SelectedMaintenanceSegment[]
  unselected_segments: SelectedMaintenanceSegment[]
  method: string
}

export interface PredictiveFactor {
  feature: string
  label: string
  contribution: number
  direction: 'increased' | 'decreased'
  importance: number
}

export interface PredictionResult {
  id?: number
  prediction_id: string
  timestamp: string
  road_segment_id: string
  model_version: string
  risk_probability: number
  risk_category: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
  predicted_future_health: number
  top_factors: PredictiveFactor[]
  urgency_recommendation: string
  feature_snapshot: Record<string, number>
}

export interface PredictiveModelMeta {
  version: string
  training_date: string
  feature_count: number
  feature_names: string[]
  training_sample_count: number
  validation_sample_count: number
  is_synthetic: boolean
  target_definition: string
  validation_metrics: {
    classifier: {
      roc_auc: number
      pr_auc: number
      precision: number
      recall: number
      f1: number
      confusion_matrix: { tn: number; fp: number; fn: number; tp: number }
    }
    regressor: {
      mae: number
      rmse: number
    }
  }
}

export interface PredictiveRiskSummary {
  total_roads_evaluated: number
  risk_counts: {
    LOW: number
    MEDIUM: number
    HIGH: number
    CRITICAL: number
  }
  avg_risk_probability: number
  latest_predictions: PredictionResult[]
}

export default apiService
