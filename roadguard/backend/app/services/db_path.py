"""
Shared database path used by all persistence services.
Reads DATABASE_URL from environment; falls back to the repo-root detections.db
for local development.
"""
from __future__ import annotations

import os
from pathlib import Path

# Environment variable takes precedence (used by Render and other cloud hosts).
# Locally defaults to the repo-root detections.db.
_env_db = os.getenv("DATABASE_URL")
if _env_db:
    DB_PATH = Path(_env_db)
    # Ensure the parent directory exists (e.g. /data on Render disk)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
else:
    DB_PATH = Path(__file__).parents[4] / "detections.db"
