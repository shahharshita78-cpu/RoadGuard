#!/usr/bin/env bash
# Render build script for RoadGuard backend.
# requirements.txt sets --index-url whl/cpu as primary, so pip resolves
# CPU-only torch/torchvision (191 MB) instead of the CUDA build (~700 MB).

set -e

echo "=== Installing Backend Dependencies (CPU-only PyTorch) ==="
pip install -r requirements.txt

if [ -n "$MODEL_DOWNLOAD_URL" ]; then
  echo "=== Downloading YOLO Model Weights ==="
  mkdir -p ../../models
  curl -L "$MODEL_DOWNLOAD_URL" -o ../../models/road_damage.pt
  echo "Model weights downloaded successfully."
else
  echo "=== Using Checked-In Model Weights ==="
  if [ -f "../../models/road_damage.pt" ]; then
    echo "Default model weights verified at models/road_damage.pt"
  else
    echo "WARNING: No model weights file found at models/road_damage.pt."
  fi
fi