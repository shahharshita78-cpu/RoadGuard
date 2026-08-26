"""
YOLO-based road damage detection service.

Wraps the Ultralytics YOLO model to produce structured detections
containing class label, confidence, and bounding-box coordinates.
The model is loaded once at application start-up and reused across requests.

Memory optimisations for Render Free tier (512 MB):
- CPU-only inference (no CUDA)
- Single-threaded PyTorch / OpenMP to avoid thread-pool overhead
- Input images are downscaled to at most MAX_SIDE pixels before inference
"""
from __future__ import annotations

import io
import os
from pathlib import Path
from typing import List, Tuple

import torch
from PIL import Image

# ── Thread / memory limits ────────────────────────────────────────────────────
# Cap PyTorch intra-op parallelism so it doesn't allocate large thread pools.
_torch_threads = int(os.getenv("TORCH_NUM_THREADS", "1"))
torch.set_num_threads(_torch_threads)
torch.set_num_interop_threads(_torch_threads)

# ── Model path ────────────────────────────────────────────────────────────────
_env_model = os.getenv("MODEL_PATH")
if _env_model:
    MODEL_PATH = Path(_env_model)
else:
    MODEL_PATH = Path(__file__).parents[4] / "models" / "road_damage.pt"

# Maximum side length for inference input.  Larger images are downscaled
# proportionally to keep peak RAM below Render's 512 MB limit.
MAX_SIDE = int(os.getenv("INFER_MAX_SIDE", "640"))

# Lazy-loaded singleton
_model = None


def _load_model():
    """Load the YOLO model from disk on first call."""
    global _model
    if _model is None:
        from ultralytics import YOLO
        _model = YOLO(str(MODEL_PATH))
    return _model


def is_model_available() -> bool:
    """Return True if the trained weights file exists on disk."""
    return MODEL_PATH.exists()


def _resize_if_needed(img: Image.Image) -> Image.Image:
    """Downscale *img* so its longest side is at most MAX_SIDE pixels."""
    w, h = img.size
    if max(w, h) > MAX_SIDE:
        scale = MAX_SIDE / max(w, h)
        new_w, new_h = int(w * scale), int(h * scale)
        img = img.resize((new_w, new_h), Image.LANCZOS)
    return img


def run_inference(
    image_bytes: bytes,
    confidence_threshold: float = 0.25,
) -> Tuple[List[dict], int, int]:
    """
    Run YOLO inference on raw image bytes.

    Returns:
        detections: list of dicts with keys damage_class, confidence, bbox
        image_width: pixel width of the *original* input image
        image_height: pixel height of the *original* input image
    """
    import gc

    model = _load_model()
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    image_width, image_height = img.size

    # Resize before inference to cap memory usage
    img_for_infer = _resize_if_needed(img)
    scale_x = image_width / img_for_infer.width
    scale_y = image_height / img_for_infer.height

    detections: List[dict] = []
    try:
        with torch.no_grad():
            results = model.predict(
                source=img_for_infer, conf=confidence_threshold, verbose=False
            )

        for result in results:
            for box in result.boxes:
                cls_id = int(box.cls[0])
                conf = float(box.conf[0])
                x1, y1, x2, y2 = (int(v) for v in box.xyxy[0].tolist())
                detections.append(
                    {
                        "damage_class": model.names[cls_id],
                        "confidence": round(conf, 4),
                        "bbox": {
                            "x1": int(x1 * scale_x),
                            "y1": int(y1 * scale_y),
                            "x2": int(x2 * scale_x),
                            "y2": int(y2 * scale_y),
                        },
                    }
                )
        # Free YOLO result tensors immediately to reclaim RAM
        del results
    finally:
        del img, img_for_infer
        gc.collect()

    return detections, image_width, image_height
