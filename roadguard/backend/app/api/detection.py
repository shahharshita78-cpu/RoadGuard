"""
Detection API endpoint.

POST /api/detect
  - Accepts a multipart image upload.
  - Runs YOLO inference.
  - Returns structured detections with severity, road health, and priority scores.
  - Optionally extracts GPS coordinates from EXIF and performs reverse geocoding.
  - Persists an inspection record to SQLite.
"""
from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from ..models.schemas import AnalysisResponse, Detection, BoundingBox
from ..services import detector, severity, scoring, optimizer, gps, inspection

router = APIRouter()


@router.post(
    "/detect",
    response_model=AnalysisResponse,
    tags=["Detection"],
    summary="Analyse a road image for damage",
)
async def detect_damage(
    file: UploadFile = File(..., description="Road image (JPEG, PNG, HEIC)"),
    confidence: float = Form(0.25, ge=0.05, le=0.95, description="Detection confidence threshold"),
    manual_lat: float = Form(None, description="Manual latitude override"),
    manual_lon: float = Form(None, description="Manual longitude override"),
) -> AnalysisResponse:
    """
    Analyse an uploaded road image for damage.

    GPS coordinates are extracted from EXIF metadata when available.
    Manual coordinates are used as fallback when provided.
    """
    if not detector.is_model_available():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="YOLO model weights not found. Place road_damage.pt in the models/ directory.",
        )

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file uploaded.")

    # Run detection
    raw_detections, img_w, img_h = detector.run_inference(file_bytes, confidence)

    # Build typed detection list
    detections = [
        Detection(
            damage_class=d["damage_class"],
            confidence=d["confidence"],
            bbox=BoundingBox(**d["bbox"]),
        )
        for d in raw_detections
    ]

    # Derived scores
    sev = severity.compute_severity(raw_detections, img_w, img_h)
    health = scoring.compute_road_health(raw_detections, img_w, img_h)
    priority = optimizer.compute_maintenance_priority(
        sev["severity_score"],
        health["road_health_score"],
        len(raw_detections),
    )

    # GPS extraction
    lat: float | None = manual_lat
    lon: float | None = manual_lon
    address: str | None = None

    exif_coords = gps.extract_gps_from_bytes(file_bytes)
    if exif_coords:
        lat, lon = exif_coords

    if lat is not None and lon is not None:
        address = gps.reverse_geocode(lat, lon)

    # Persist inspection
    inspection.create_inspection(
        image_name=file.filename or "upload",
        detections=raw_detections,
        severity_score=sev["severity_score"],
        severity=sev["severity"],
        road_health_score=health["road_health_score"],
        road_condition=health["road_condition"],
        priority_score=priority["priority_score"],
        priority=priority["priority"],
        latitude=lat,
        longitude=lon,
        address=address,
    )

    return AnalysisResponse(
        detections=detections,
        image_width=img_w,
        image_height=img_h,
        detection_count=len(detections),
        severity=sev,
        road_health=health,
        maintenance_priority=priority,
        latitude=lat,
        longitude=lon,
        address=address,
    )
