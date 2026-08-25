"""
Video Road Inspection Service (Phase 11).

Processes a video file frame-by-frame using configurable sampling, runs the
existing YOLO detector on each sampled frame, and aggregates the results into
a structured inspection summary.

Key design decisions
--------------------
* **No full-video memory load** — cv2.VideoCapture reads frames lazily; only
  the current frame is held in memory at any time.
* **Temporal deduplication** — consecutive detections of the same damage class
  whose bounding boxes overlap significantly (IoU >= 0.45) are treated as the
  same physical defect and not double-counted in the aggregated totals.  The
  de-dup window is limited to the immediately preceding sampled frame so it
  stays O(1) per frame and requires no tracking library.
* **Reuse of existing services** — severity, road health, and maintenance
  priority are all computed via the existing service functions with no
  duplication of formula logic.
* **Persistence** — summaries are stored in the existing SQLite database in a
  dedicated ``video_inspections`` table created by ``ensure_video_schema()``.
"""
from __future__ import annotations

import io
import json
import sqlite3
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

from PIL import Image

from .severity import compute_severity
from .scoring import compute_road_health
from .optimizer import compute_maintenance_priority
from .detector import _load_model  # imported here so tests can patch via this module's namespace

# Reuse the same DB file as the image inspection service.
DB_PATH = Path(__file__).parents[4] / "detections.db"

# Supported video MIME types / extensions OpenCV can handle.
SUPPORTED_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm", ".m4v", ".mpeg", ".mpg"}

# Default frame sampling interval.
DEFAULT_FRAME_INTERVAL = 30  # process every 30th frame (~1 fps for 30 fps video)

# IoU threshold above which two bounding boxes are considered the same defect.
DEDUP_IOU_THRESHOLD = 0.45


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def _get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_video_schema() -> None:
    """Create the video_inspections table if it does not exist."""
    conn = _get_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS video_inspections (
            id                      INTEGER PRIMARY KEY AUTOINCREMENT,
            inspection_id           TEXT UNIQUE NOT NULL,
            timestamp               TEXT NOT NULL,
            video_name              TEXT,
            duration_seconds        REAL,
            total_frames            INTEGER DEFAULT 0,
            sampled_frames          INTEGER DEFAULT 0,
            frame_interval          INTEGER DEFAULT 30,
            fps                     REAL,
            total_detections        INTEGER DEFAULT 0,
            unique_detections       INTEGER DEFAULT 0,
            frames_with_damage      INTEGER DEFAULT 0,
            damage_frame_pct        REAL DEFAULT 0,
            avg_confidence          REAL DEFAULT 0,
            avg_severity_score      INTEGER DEFAULT 0,
            max_severity_score      INTEGER DEFAULT 0,
            overall_severity        TEXT,
            road_health_score       INTEGER DEFAULT 100,
            road_condition          TEXT,
            priority_score          INTEGER DEFAULT 0,
            priority                TEXT,
            class_distribution      TEXT,   -- JSON object
            frame_summaries         TEXT,   -- JSON array (abbreviated)
            priority_reasons        TEXT    -- JSON array
        )
        """
    )
    conn.commit()
    conn.close()


def save_video_inspection(record: dict) -> dict:
    """Persist a video inspection result and return the saved row."""
    ensure_video_schema()
    conn = _get_connection()
    conn.execute(
        """
        INSERT INTO video_inspections (
            inspection_id, timestamp, video_name, duration_seconds,
            total_frames, sampled_frames, frame_interval, fps,
            total_detections, unique_detections, frames_with_damage,
            damage_frame_pct, avg_confidence, avg_severity_score,
            max_severity_score, overall_severity, road_health_score,
            road_condition, priority_score, priority,
            class_distribution, frame_summaries, priority_reasons
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            record["inspection_id"],
            record["timestamp"],
            record["video_name"],
            record["duration_seconds"],
            record["total_frames"],
            record["sampled_frames"],
            record["frame_interval"],
            record["fps"],
            record["total_detections"],
            record["unique_detections"],
            record["frames_with_damage"],
            record["damage_frame_pct"],
            record["avg_confidence"],
            record["avg_severity_score"],
            record["max_severity_score"],
            record["overall_severity"],
            record["road_health_score"],
            record["road_condition"],
            record["priority_score"],
            record["priority"],
            json.dumps(record["class_distribution"]),
            json.dumps(record["frame_summaries"]),
            json.dumps(record.get("priority_reasons", [])),
        ),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM video_inspections WHERE inspection_id = ?",
        (record["inspection_id"],),
    ).fetchone()
    conn.close()
    return _deserialise_row(dict(row))


def get_all_video_inspections() -> List[dict]:
    """Return all video inspection records, newest first."""
    ensure_video_schema()
    conn = _get_connection()
    rows = conn.execute(
        "SELECT * FROM video_inspections ORDER BY timestamp DESC"
    ).fetchall()
    conn.close()
    return [_deserialise_row(dict(r)) for r in rows]


def get_video_inspection_by_id(inspection_id: str) -> Optional[dict]:
    """Return a single video inspection by UUID, or None."""
    ensure_video_schema()
    conn = _get_connection()
    row = conn.execute(
        "SELECT * FROM video_inspections WHERE inspection_id = ?",
        (inspection_id,),
    ).fetchone()
    conn.close()
    return _deserialise_row(dict(row)) if row else None


def _deserialise_row(row: dict) -> dict:
    """Parse JSON blob columns back to Python objects."""
    for key in ("class_distribution", "frame_summaries", "priority_reasons"):
        raw = row.get(key)
        if isinstance(raw, str):
            try:
                row[key] = json.loads(raw)
            except (ValueError, TypeError):
                row[key] = {} if key == "class_distribution" else []
    return row


# ---------------------------------------------------------------------------
# Bounding-box IoU helper (for temporal deduplication)
# ---------------------------------------------------------------------------

def _iou(a: dict, b: dict) -> float:
    """Compute Intersection-over-Union for two bbox dicts {x1,y1,x2,y2}."""
    ix1 = max(a["x1"], b["x1"])
    iy1 = max(a["y1"], b["y1"])
    ix2 = min(a["x2"], b["x2"])
    iy2 = min(a["y2"], b["y2"])
    inter_w = max(0, ix2 - ix1)
    inter_h = max(0, iy2 - iy1)
    inter = inter_w * inter_h
    if inter == 0:
        return 0.0
    area_a = max(1, (a["x2"] - a["x1"]) * (a["y2"] - a["y1"]))
    area_b = max(1, (b["x2"] - b["x1"]) * (b["y2"] - b["y1"]))
    return inter / (area_a + area_b - inter)


def _is_duplicate(
    det: dict,
    prev_frame_dets: List[dict],
    iou_threshold: float = DEDUP_IOU_THRESHOLD,
) -> bool:
    """
    Return True if *det* closely overlaps a detection in the previous sampled
    frame (same class + high IoU), indicating the same physical defect.
    """
    for prev in prev_frame_dets:
        if prev["damage_class"] != det["damage_class"]:
            continue
        if _iou(det["bbox"], prev["bbox"]) >= iou_threshold:
            return True
    return False


# ---------------------------------------------------------------------------
# Core processing
# ---------------------------------------------------------------------------

def _frame_to_bytes(frame_bgr) -> bytes:
    """Convert a BGR OpenCV frame to JPEG bytes via PIL."""
    import numpy as np
    # Convert BGR → RGB
    frame_rgb = frame_bgr[:, :, ::-1]
    img = Image.fromarray(frame_rgb.astype("uint8"))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def process_video(
    video_path: Path,
    video_name: str,
    frame_interval: int = DEFAULT_FRAME_INTERVAL,
    confidence_threshold: float = 0.25,
) -> dict:
    """
    Process a video file and return a structured inspection result.

    Parameters
    ----------
    video_path : Path
        Absolute path to the video file (temporary file written by the API).
    video_name : str
        Original filename reported by the client (for display).
    frame_interval : int
        Sample one frame every *frame_interval* frames.
    confidence_threshold : float
        Minimum confidence score for a detection to be retained.

    Returns
    -------
    dict
        Fully structured inspection result ready for persistence and API response.

    Raises
    ------
    ValueError
        If the file cannot be opened as a video or yields no readable frames.
    """
    try:
        import cv2  # opencv-python is already in requirements
    except ImportError as exc:
        raise ImportError("opencv-python is required for video processing.") from exc

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise ValueError(f"Cannot open video file: {video_name}")

    fps: float = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames: int = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    duration_seconds: float = total_frames / fps if fps > 0 else 0.0

    model = _load_model()

    # Per-sampled-frame results
    frame_summaries: List[dict] = []

    # Running aggregates
    all_detections: List[dict] = []  # includes duplicates (raw total)
    unique_detections: List[dict] = []  # after temporal dedup
    severity_scores: List[int] = []
    frames_with_damage: int = 0
    sampled_count: int = 0
    prev_frame_dets: List[dict] = []
    frame_idx: int = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_idx % frame_interval != 0:
            frame_idx += 1
            continue

        # --- Run inference on this frame ---
        h, w = frame.shape[:2]
        frame_bytes = _frame_to_bytes(frame)
        img = Image.open(io.BytesIO(frame_bytes)).convert("RGB")

        results = model.predict(source=img, conf=confidence_threshold, verbose=False)
        frame_dets: List[dict] = []
        for result in results:
            for box in result.boxes:
                cls_id = int(box.cls[0])
                conf = float(box.conf[0])
                x1, y1, x2, y2 = (int(v) for v in box.xyxy[0].tolist())
                frame_dets.append(
                    {
                        "damage_class": model.names[cls_id],
                        "confidence": round(conf, 4),
                        "bbox": {"x1": x1, "y1": y1, "x2": x2, "y2": y2},
                    }
                )

        # --- Compute per-frame scores ---
        frame_sev = compute_severity(frame_dets, w, h)
        frame_health = compute_road_health(frame_dets, w, h)
        timestamp_sec = frame_idx / fps if fps > 0 else 0.0

        frame_summary = {
            "frame_number": frame_idx,
            "timestamp_sec": round(timestamp_sec, 2),
            "detection_count": len(frame_dets),
            "severity_score": frame_sev["severity_score"],
            "road_health_score": frame_health["road_health_score"],
            "damage_classes": list({d["damage_class"] for d in frame_dets}),
        }
        frame_summaries.append(frame_summary)

        # --- Accumulate ---
        all_detections.extend(frame_dets)
        severity_scores.append(frame_sev["severity_score"])

        if frame_dets:
            frames_with_damage += 1

        # Temporal deduplication: only add if NOT a carry-over from previous frame
        for det in frame_dets:
            if not _is_duplicate(det, prev_frame_dets):
                unique_detections.append(det)

        prev_frame_dets = frame_dets
        sampled_count += 1
        frame_idx += 1

    cap.release()

    if sampled_count == 0:
        raise ValueError("Video contains no readable frames.")

    # --- Aggregate scores across all unique detections ---
    # Use a representative image size; fall back to 640x480 if no frames were read
    rep_w, rep_h = (640, 480)
    if frame_summaries:
        # We cannot recover frame dimensions here easily; use full-HD estimate
        # or last known frame size.  For scoring purposes, relative area matters.
        rep_w, rep_h = 1280, 720

    overall_sev = compute_severity(unique_detections, rep_w, rep_h)
    overall_health = compute_road_health(unique_detections, rep_w, rep_h)
    overall_priority = compute_maintenance_priority(
        overall_sev["severity_score"],
        overall_health["road_health_score"],
        len(unique_detections),
    )

    # Class distribution (from unique detections only)
    class_dist: dict = {}
    for det in unique_detections:
        cls = det["damage_class"]
        class_dist[cls] = class_dist.get(cls, 0) + 1

    # Average confidence
    all_confs = [d["confidence"] for d in all_detections]
    avg_conf = round(sum(all_confs) / len(all_confs), 4) if all_confs else 0.0

    # Average / max severity across sampled frames
    avg_sev = int(round(sum(severity_scores) / len(severity_scores))) if severity_scores else 0
    max_sev = max(severity_scores) if severity_scores else 0

    damage_frame_pct = round((frames_with_damage / sampled_count) * 100, 1)

    return {
        "inspection_id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "video_name": video_name,
        "duration_seconds": round(duration_seconds, 2),
        "total_frames": total_frames,
        "sampled_frames": sampled_count,
        "frame_interval": frame_interval,
        "fps": round(fps, 2),
        "total_detections": len(all_detections),
        "unique_detections": len(unique_detections),
        "frames_with_damage": frames_with_damage,
        "damage_frame_pct": damage_frame_pct,
        "avg_confidence": avg_conf,
        "avg_severity_score": avg_sev,
        "max_severity_score": max_sev,
        "overall_severity": overall_sev["severity"],
        "road_health_score": overall_health["road_health_score"],
        "road_condition": overall_health["road_condition"],
        "priority_score": overall_priority["priority_score"],
        "priority": overall_priority["priority"],
        "priority_reasons": overall_priority["reasons"],
        "class_distribution": class_dist,
        "frame_summaries": frame_summaries,
    }
