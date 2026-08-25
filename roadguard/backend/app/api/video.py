"""
Video inspection API endpoints (Phase 11).

POST /api/video/detect             — Upload a video, run YOLO frame sampling,
                                     return aggregated road inspection result.
GET  /api/video/inspections        — List all previous video inspections.
GET  /api/video/inspections/{id}   — Retrieve one video inspection by UUID.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from ..services import video_inspection as vi_svc
from ..services.detector import is_model_available

router = APIRouter()


def _validate_video_extension(filename: str) -> None:
    """Raise HTTP 415 if the file extension is not supported."""
    ext = Path(filename).suffix.lower()
    if ext not in vi_svc.SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"Unsupported file type '{ext}'. "
                f"Accepted formats: {', '.join(sorted(vi_svc.SUPPORTED_EXTENSIONS))}"
            ),
        )


@router.post(
    "/video/detect",
    tags=["Video Inspection"],
    summary="Process a road video for damage assessment",
)
async def video_detect(
    file: UploadFile = File(..., description="Road video file (MP4, AVI, MOV, MKV, WEBM, M4V)"),
    frame_interval: int = Form(
        vi_svc.DEFAULT_FRAME_INTERVAL,
        ge=1,
        le=300,
        description="Process every N-th frame (default 30)",
    ),
    confidence: float = Form(
        0.25,
        ge=0.05,
        le=0.95,
        description="YOLO confidence threshold",
    ),
) -> Dict[str, Any]:
    """
    Upload a road video to detect surface damage across sampled frames.

    The endpoint:
    1. Validates the file extension.
    2. Writes the upload to a temporary file (avoids loading the full video
       into memory as bytes).
    3. Runs the existing YOLO detector on every N-th frame.
    4. Aggregates detections with temporal deduplication.
    5. Computes severity, Road Health Index, and maintenance priority.
    6. Persists the summary to SQLite and returns the full result.
    """
    if not is_model_available():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="YOLO model weights not found. Place road_damage.pt in models/.",
        )

    filename = file.filename or "upload.mp4"
    _validate_video_extension(filename)

    # Stream the upload to a temporary file — avoids holding the whole video
    # in memory at once.
    suffix = Path(filename).suffix.lower()
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp_path = Path(tmp.name)
        chunk_size = 1024 * 1024  # 1 MB chunks
        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break
            tmp.write(chunk)

    try:
        result = vi_svc.process_video(
            video_path=tmp_path,
            video_name=filename,
            frame_interval=frame_interval,
            confidence_threshold=confidence,
        )
    except ValueError as exc:
        tmp_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    except Exception as exc:
        tmp_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Video processing failed: {exc}",
        )
    finally:
        tmp_path.unlink(missing_ok=True)

    saved = vi_svc.save_video_inspection(result)
    return saved


@router.get(
    "/video/inspections",
    tags=["Video Inspection"],
    summary="List all previous video inspections",
)
def list_video_inspections() -> List[Dict[str, Any]]:
    """Return all stored video inspection records, newest first."""
    return vi_svc.get_all_video_inspections()


@router.get(
    "/video/inspections/{inspection_id}",
    tags=["Video Inspection"],
    summary="Retrieve a single video inspection by UUID",
)
def get_video_inspection(inspection_id: str) -> Dict[str, Any]:
    """Return the video inspection record with the given UUID."""
    record = vi_svc.get_video_inspection_by_id(inspection_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Video inspection '{inspection_id}' not found.",
        )
    return record
