"""
Shared database path used by all persistence services.
Reads ROADGUARD_DB_PATH from environment. If not provided, defaults to:
- /tmp/roadguard/detections.db on Linux (writable on Render Free tier)
- repo-root detections.db on Windows (local zero-config development)
"""
from __future__ import annotations

import os
import platform
from pathlib import Path

_env_db = os.getenv("ROADGUARD_DB_PATH")
if _env_db:
    DB_PATH = Path(_env_db)
else:
    if platform.system() == "Windows":
        DB_PATH = Path(__file__).parents[4] / "detections.db"
    else:
        DB_PATH = Path("/tmp/roadguard/detections.db")

# Ensure the parent directory exists (e.g. /tmp/roadguard on Render)
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
