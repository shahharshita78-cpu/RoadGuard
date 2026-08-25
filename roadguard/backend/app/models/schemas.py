"""
Pydantic schemas for RoadGuard API request and response models.
"""
from __future__ import annotations

from pydantic import ConfigDict

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Detection schemas
# ---------------------------------------------------------------------------

class BoundingBox(BaseModel):
    x1: int = Field(..., description="Left pixel coordinate")
    y1: int = Field(..., description="Top pixel coordinate")
    x2: int = Field(..., description="Right pixel coordinate")
    y2: int = Field(..., description="Bottom pixel coordinate")


class Detection(BaseModel):
    damage_class: str = Field(..., description="Damage class label (D00, D10, D20, D40)")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Detector confidence score")
    bbox: BoundingBox


class DetectionResponse(BaseModel):
    detections: List[Detection]
    image_width: int
    image_height: int
    detection_count: int


# ---------------------------------------------------------------------------
# Severity schemas
# ---------------------------------------------------------------------------

class SeverityResponse(BaseModel):
    severity_score: int = Field(..., ge=0, le=100)
    severity: str = Field(..., description="Low | Medium | High")


# ---------------------------------------------------------------------------
# Road Health Index schemas
# ---------------------------------------------------------------------------

class RoadHealthResponse(BaseModel):
    road_health_score: int = Field(..., ge=0, le=100)
    road_condition: str = Field(..., description="Excellent | Good | Moderate | Poor | Critical")


# ---------------------------------------------------------------------------
# Maintenance Priority schemas
# ---------------------------------------------------------------------------

class MaintenancePriorityResponse(BaseModel):
    priority_score: int = Field(..., ge=0, le=100)
    priority: str = Field(..., description="Routine | Medium | High | Immediate")
    reasons: List[str]


# ---------------------------------------------------------------------------
# Full analysis response (detection + derived scores)
# ---------------------------------------------------------------------------

class AnalysisResponse(BaseModel):
    detections: List[Detection]
    image_width: int
    image_height: int
    detection_count: int
    severity: SeverityResponse
    road_health: RoadHealthResponse
    maintenance_priority: MaintenancePriorityResponse
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    address: Optional[str] = None


# ---------------------------------------------------------------------------
# Inspection record schemas
# ---------------------------------------------------------------------------

class InspectionCreate(BaseModel):
    image_name: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    address: Optional[str] = None
    detections: List[Detection]
    severity_score: int
    severity: str
    road_health_score: int
    road_condition: str
    priority_score: int
    priority: str


class InspectionRecord(BaseModel):
    id: int
    inspection_id: str
    timestamp: datetime
    image_name: str
    latitude: Optional[float]
    longitude: Optional[float]
    address: Optional[str]
    damage_classes: str
    detection_count: int
    severity_score: int
    severity: str
    road_health_score: int
    road_condition: str
    priority_score: int
    priority: str

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Health check schema
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    version: str
