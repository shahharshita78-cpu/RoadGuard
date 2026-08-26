#!/usr/bin/env bash
# Render build script for RoadGuard backend web service.
# Installs CPU-only PyTorch first to avoid pulling the heavy CUDA stack,
# then installs remaining packages and fetches YOLO weights if a URL is provided.

set -e

echo "=== Installing CPU-only PyTorch (avoids 2 GB CUDA wheel) ==="
pip install --index-url https://download.pytorch.org/whl/cpu \
    "torch>=2.0.0,<3.0.0" \
    "torchvision>=0.15.0,<1.0.0"

echo "=== Installing Backend Dependencies ==="
pip install -r requirements.txt --no-deps --ignore-requires-python 2>/dev/null || \
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
    echo "WARNING: No model weights file found at models/road_damage.pt. Verify deployment."
  fi
fi
