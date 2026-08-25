"""
Inspection record service — SQLite persistence layer.

Schema:
    inspections (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        inspection_id   TEXT UNIQUE,         -- UUID
        timestamp       TEXT,                -- ISO-8601
        image_name      TEXT,
        latitude        REAL,
        longitude       REAL,
        address         TEXT,
        damage_classes  TEXT,                -- JSON array as string
        detection_count INTEGER,
        severity_score  INTEGER,
        severity        TEXT,
        road_health_score INTEGER,
        road_condition  TEXT,
        priority_score  INTEGER,
        priority        TEXT
    )
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

DB_PATH = Path(__file__).parents[4] / "detections.db"


def _get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_schema() -> None:
    """Create the inspections table if it does not exist."""
    conn = _get_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS inspections (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            inspection_id    TEXT UNIQUE NOT NULL,
            timestamp        TEXT NOT NULL,
            image_name       TEXT,
            latitude         REAL,
            longitude        REAL,
            address          TEXT,
            damage_classes   TEXT,
            detection_count  INTEGER DEFAULT 0,
            severity_score   INTEGER DEFAULT 0,
            severity         TEXT,
            road_health_score INTEGER DEFAULT 100,
            road_condition   TEXT,
            priority_score   INTEGER DEFAULT 0,
            priority         TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def create_inspection(
    image_name: str,
    detections: List[dict],
    severity_score: int,
    severity: str,
    road_health_score: int,
    road_condition: str,
    priority_score: int,
    priority: str,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    address: Optional[str] = None,
) -> dict:
    """Insert a new inspection record and return it."""
    ensure_schema()
    inspection_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()
    damage_classes = json.dumps(list({d["damage_class"] for d in detections}))
    detection_count = len(detections)

    conn = _get_connection()
    conn.execute(
        """
        INSERT INTO inspections
            (inspection_id, timestamp, image_name, latitude, longitude, address,
             damage_classes, detection_count, severity_score, severity,
             road_health_score, road_condition, priority_score, priority)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            inspection_id, timestamp, image_name,
            latitude, longitude, address,
            damage_classes, detection_count,
            severity_score, severity,
            road_health_score, road_condition,
            priority_score, priority,
        ),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM inspections WHERE inspection_id = ?", (inspection_id,)
    ).fetchone()
    conn.close()
    return dict(row)


def get_all_inspections() -> List[dict]:
    """Return all inspection records ordered newest first."""
    ensure_schema()
    conn = _get_connection()
    rows = conn.execute(
        "SELECT * FROM inspections ORDER BY timestamp DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_inspection_by_id(inspection_id: str) -> Optional[dict]:
    """Return a single inspection record by its UUID, or None."""
    ensure_schema()
    conn = _get_connection()
    row = conn.execute(
        "SELECT * FROM inspections WHERE inspection_id = ?", (inspection_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None
