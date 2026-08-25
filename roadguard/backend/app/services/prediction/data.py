"""
Data loading service for RoadGuard Predictive Analytics.
Loads historical longitudinal data, falling back to generating synthetic data if needed.
"""
from __future__ import annotations

from pathlib import Path
import pandas as pd
import subprocess
import sys

# Paths
SERVICE_DIR = Path(__file__).resolve().parent
ROOT_DIR = SERVICE_DIR.parents[4]
DEFAULT_CSV_PATH = ROOT_DIR / "data" / "synthetic_inspections.csv"
GENERATOR_SCRIPT = ROOT_DIR / "scripts" / "generate_prediction_dataset.py"


def load_raw_dataset(csv_path: Path = DEFAULT_CSV_PATH) -> pd.DataFrame:
    """
    Load the longitudinal dataset from CSV.
    If the file does not exist, automatically invoke the synthetic dataset generator.
    """
    if not csv_path.exists():
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        # Run synthetic data generator to create prototype dataset
        cmd = [sys.executable, str(GENERATOR_SCRIPT), "--output", str(csv_path)]
        try:
            subprocess.run(cmd, check=True, capture_output=True)
        except subprocess.CalledProcessError as err:
            raise RuntimeError(f"Failed to generate synthetic data: {err.stderr.decode().strip()}") from err

    df = pd.read_csv(csv_path)
    return df
