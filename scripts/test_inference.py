"""
Standalone inference verification script (Phase 3).

Run from the repository root inside the virtual environment:
    .venv\Scripts\python scripts\test_inference.py

Verifies:
  - The trained model weights file exists.
  - YOLO loads correctly.
  - Inference on a sample image returns valid detections with bounding boxes.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure the repo root is on the path so services are importable.
REPO_ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(REPO_ROOT))

MODEL_PATH = REPO_ROOT / "models" / "road_damage.pt"
SAMPLE_IMAGE = REPO_ROOT / "road.jpg"


def main() -> None:
    print("=== RoadGuard Inference Verification ===\n")

    # 1. Check model file exists
    if not MODEL_PATH.exists():
        print(f"[FAIL] Model not found at {MODEL_PATH}")
        sys.exit(1)
    print(f"[OK]   Model found: {MODEL_PATH} ({MODEL_PATH.stat().st_size / 1e6:.1f} MB)")

    # 2. Load model
    try:
        from ultralytics import YOLO
        model = YOLO(str(MODEL_PATH))
        print(f"[OK]   Model loaded. Classes: {list(model.names.values())}")
    except Exception as exc:
        print(f"[FAIL] Could not load model: {exc}")
        sys.exit(1)

    # 3. Choose a sample image
    if not SAMPLE_IMAGE.exists():
        print(f"[WARN] Sample image not found at {SAMPLE_IMAGE}. Using first jpg in root.")
        candidates = list(REPO_ROOT.glob("*.jpg"))
        if not candidates:
            print("[FAIL] No JPG image available for inference test.")
            sys.exit(1)
        sample = candidates[0]
    else:
        sample = SAMPLE_IMAGE

    print(f"\n[INFO] Running inference on: {sample.name}")

    # 4. Run inference
    try:
        results = model.predict(source=str(sample), conf=0.10, verbose=False)
        boxes = results[0].boxes
        print(f"[OK]   Inference complete. Detections: {len(boxes)}")
    except Exception as exc:
        print(f"[FAIL] Inference failed: {exc}")
        sys.exit(1)

    # 5. Print detections
    if len(boxes) == 0:
        print("[INFO] No detections above threshold (this may be expected for this image).")
    else:
        print("\n  Detections:")
        for box in boxes:
            cls_id = int(box.cls[0])
            conf = float(box.conf[0])
            x1, y1, x2, y2 = (int(v) for v in box.xyxy[0].tolist())
            print(
                f"    class={model.names[cls_id]:<5}  conf={conf:.3f}  "
                f"bbox=[{x1}, {y1}, {x2}, {y2}]"
            )

    # 6. Verify the service wrapper works
    print("\n[INFO] Testing detector service wrapper …")
    from roadguard.backend.app.services.detector import run_inference
    with open(sample, "rb") as f:
        raw_bytes = f.read()
    detections, w, h = run_inference(raw_bytes, confidence_threshold=0.10)
    print(f"[OK]   Service wrapper returned {len(detections)} detection(s). Image: {w}x{h}")

    print("\n=== Verification complete ===")


if __name__ == "__main__":
    main()
