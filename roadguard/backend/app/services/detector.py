"""
YOLO-based road damage detection service — ONNX Runtime backend.

Uses onnxruntime-cpu instead of PyTorch + ultralytics to keep
the memory footprint under Render's 512 MB free-tier limit.

PyTorch CPU: ~300 MB RSS   →  onnxruntime-cpu: ~80 MB RSS

The model is loaded once at first inference and reused across requests.
Input images are resized to at most MAX_SIDE pixels to cap per-request
peak memory; bounding boxes are scaled back to original resolution.
"""
from __future__ import annotations

import gc
import io
import os
from pathlib import Path
from typing import List, Tuple

import numpy as np
from PIL import Image

# ── Model path ────────────────────────────────────────────────────────────────
_env_model = os.getenv("MODEL_PATH")
if _env_model:
    _base = Path(_env_model)
    # Accept either .pt or .onnx as the configured path; prefer .onnx
    MODEL_PATH = _base.with_suffix(".onnx") if _base.suffix == ".pt" else _base
else:
    _models_dir = Path(__file__).parents[4] / "models"
    MODEL_PATH = _models_dir / "road_damage.onnx"

# Fallback to .pt path so is_model_available() reports correctly when only
# the PyTorch weights are present (e.g., before the first ONNX export).
_PT_FALLBACK = MODEL_PATH.with_suffix(".pt")

# Maximum longest side for inference input — keeps peak RAM bounded.
MAX_SIDE = int(os.getenv("INFER_MAX_SIDE", "640"))

# YOLO class names embedded here so we don't need ultralytics at runtime.
# These must match the class order in road_damage.onnx / road_damage.pt.
_DEFAULT_CLASS_NAMES = [
    "D00", "D01", "D10", "D11", "D20", "D40", "D43", "D44",
    "pothole", "crack", "alligator_crack", "rutting",
]

# Lazy-loaded singletons
_session = None          # onnxruntime.InferenceSession
_class_names: List[str] = _DEFAULT_CLASS_NAMES


def _load_session():
    """Load ONNX Runtime inference session on first call."""
    global _session, _class_names
    if _session is not None:
        return _session

    import onnxruntime as ort

    # Limit ort thread count to reduce RSS on Render free tier
    so = ort.SessionOptions()
    so.intra_op_num_threads = int(os.getenv("TORCH_NUM_THREADS", "1"))
    so.inter_op_num_threads = int(os.getenv("TORCH_NUM_THREADS", "1"))
    so.log_severity_level = 3  # ERROR only — suppress verbose init output

    _session = ort.InferenceSession(
        str(MODEL_PATH),
        sess_options=so,
        providers=["CPUExecutionProvider"],
    )

    # Try to read class names from ONNX metadata (ultralytics stores them there)
    try:
        meta = _session.get_modelmeta().custom_metadata_map
        if "names" in meta:
            import ast
            names_raw = meta["names"]
            parsed = ast.literal_eval(names_raw)
            if isinstance(parsed, dict):
                _class_names = [parsed[i] for i in sorted(parsed)]
            elif isinstance(parsed, list):
                _class_names = parsed
    except Exception:
        pass  # keep defaults

    return _session


class YOLOONNXWrapper:
    def __init__(self):
        _load_session()
        self.names = _class_names

    def predict(self, source, conf=0.25, verbose=False):
        if isinstance(source, Image.Image):
            img = source
        else:
            img = Image.open(source) if isinstance(source, (str, Path)) else source

        image_width, image_height = img.size
        img_for_infer = _resize_if_needed(img)
        scale_x = image_width / img_for_infer.width
        scale_y = image_height / img_for_infer.height

        inp = _preprocess(img_for_infer)
        session = _load_session()
        input_name = session.get_inputs()[0].name
        outputs = session.run(None, {input_name: inp})
        raw = outputs[0]
        if raw.ndim == 3:
            raw = raw[0]
        if raw.shape[0] < raw.shape[1]:
            raw = raw.T

        num_classes = len(_class_names)
        boxes_cxcywh = raw[:, :4]
        class_scores = raw[:, 4:4 + num_classes]

        cls_ids = class_scores.argmax(axis=1)
        confs = class_scores.max(axis=1)
        mask = confs >= conf
        boxes_cxcywh = boxes_cxcywh[mask]
        confs = confs[mask]
        cls_ids = cls_ids[mask]

        cx, cy, bw, bh = boxes_cxcywh[:, 0], boxes_cxcywh[:, 1], boxes_cxcywh[:, 2], boxes_cxcywh[:, 3]
        x1 = cx - bw / 2
        y1 = cy - bh / 2
        x2 = cx + bw / 2
        y2 = cy + bh / 2
        boxes_xyxy = np.stack([x1, y1, x2, y2], axis=1)

        keep = _nms(boxes_xyxy, confs)

        class MockTensor:
            def __init__(self, val):
                self.val = val
            def tolist(self):
                return self.val

        class MockBox:
            def __init__(self, cls_id, confidence, bbox_coords):
                self.cls = [cls_id]
                self.conf = [confidence]
                self.xyxy = [MockTensor(bbox_coords)]

        class MockResult:
            def __init__(self, boxes):
                self.boxes = boxes

        sx = image_width / MAX_SIDE
        sy = image_height / MAX_SIDE

        boxes_list = []
        for idx in keep:
            x1_s = max(0, int(boxes_xyxy[idx, 0] * sx))
            y1_s = max(0, int(boxes_xyxy[idx, 1] * sy))
            x2_s = min(image_width, int(boxes_xyxy[idx, 2] * sx))
            y2_s = min(image_height, int(boxes_xyxy[idx, 3] * sy))
            boxes_list.append(MockBox(cls_ids[idx], confs[idx], [x1_s, y1_s, x2_s, y2_s]))

        return [MockResult(boxes_list)]

_load_model_wrapper_instance = None

def _load_model():
    global _load_model_wrapper_instance
    if _load_model_wrapper_instance is None:
        _load_model_wrapper_instance = YOLOONNXWrapper()
    return _load_model_wrapper_instance



def is_model_available() -> bool:
    """Return True if the ONNX (or PyTorch fallback) model file exists."""
    return MODEL_PATH.exists() or _PT_FALLBACK.exists()



def _resize_if_needed(img: Image.Image) -> Image.Image:
    """Downscale *img* so its longest side is at most MAX_SIDE pixels."""
    w, h = img.size
    if max(w, h) > MAX_SIDE:
        scale = MAX_SIDE / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    return img


def _preprocess(img: Image.Image) -> np.ndarray:
    """Convert PIL image to normalised float32 NCHW array for YOLO."""
    img = img.resize((MAX_SIDE, MAX_SIDE), Image.LANCZOS)
    arr = np.array(img, dtype=np.float32) / 255.0   # HWC, [0,1]
    arr = arr.transpose(2, 0, 1)                     # CHW
    return arr[np.newaxis]                           # NCHW


def _nms(boxes: np.ndarray, scores: np.ndarray, iou_thresh: float = 0.45) -> List[int]:
    """Non-maximum suppression (pure NumPy, no torch dependency)."""
    if len(boxes) == 0:
        return []
    x1, y1, x2, y2 = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
    areas = (x2 - x1) * (y2 - y1)
    order = scores.argsort()[::-1]
    keep: List[int] = []
    while len(order):
        i = order[0]
        keep.append(int(i))
        if len(order) == 1:
            break
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        inter = np.maximum(0.0, xx2 - xx1) * np.maximum(0.0, yy2 - yy1)
        iou = inter / (areas[i] + areas[order[1:]] - inter + 1e-6)
        order = order[1:][iou <= iou_thresh]
    return keep


def run_inference(
    image_bytes: bytes,
    confidence_threshold: float = 0.25,
) -> Tuple[List[dict], int, int]:
    """
    Run YOLO inference on raw image bytes via ONNX Runtime.

    Returns:
        detections: list of dicts with keys damage_class, confidence, bbox
        image_width: pixel width of the *original* input image
        image_height: pixel height of the *original* input image
    """
    session = _load_session()

    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    image_width, image_height = img.size

    # Build input tensor
    inp = _preprocess(img)
    del img

    # Run inference
    input_name = session.get_inputs()[0].name
    try:
        outputs = session.run(None, {input_name: inp})
    finally:
        del inp
        gc.collect()

    # YOLOv8 ONNX output shape: [1, num_classes+4, num_anchors]
    # Each column: [cx, cy, w, h, cls0_score, cls1_score, ...]
    raw = outputs[0]                      # shape (1, 4+C, N) or (1, N, 4+C)
    del outputs

    # Normalise to (N, 4+C)
    if raw.ndim == 3:
        raw = raw[0]                      # (4+C, N) or (N, 4+C)
    if raw.shape[0] < raw.shape[1]:
        raw = raw.T                       # ensure (N, 4+C)

    num_classes = len(_class_names)
    boxes_cxcywh = raw[:, :4]
    class_scores = raw[:, 4:4 + num_classes]

    cls_ids = class_scores.argmax(axis=1)
    confs = class_scores.max(axis=1)
    mask = confs >= confidence_threshold
    boxes_cxcywh = boxes_cxcywh[mask]
    confs = confs[mask]
    cls_ids = cls_ids[mask]

    # Convert cx,cy,w,h → x1,y1,x2,y2 (in 640-pixel space)
    cx, cy, bw, bh = boxes_cxcywh[:, 0], boxes_cxcywh[:, 1], boxes_cxcywh[:, 2], boxes_cxcywh[:, 3]
    x1 = cx - bw / 2
    y1 = cy - bh / 2
    x2 = cx + bw / 2
    y2 = cy + bh / 2
    boxes_xyxy = np.stack([x1, y1, x2, y2], axis=1)

    # NMS
    keep = _nms(boxes_xyxy, confs)

    # Scale bounding boxes back to original image size
    sx = image_width / MAX_SIDE
    sy = image_height / MAX_SIDE

    detections: List[dict] = []
    for i in keep:
        detections.append({
            "damage_class": _class_names[cls_ids[i]],
            "confidence": round(float(confs[i]), 4),
            "bbox": {
                "x1": max(0, int(boxes_xyxy[i, 0] * sx)),
                "y1": max(0, int(boxes_xyxy[i, 1] * sy)),
                "x2": min(image_width, int(boxes_xyxy[i, 2] * sx)),
                "y2": min(image_height, int(boxes_xyxy[i, 3] * sy)),
            },
        })

    return detections, image_width, image_height
