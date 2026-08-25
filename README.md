# RoadGuard — Road Infrastructure Intelligence Platform

A portfolio-grade, production-structured system for automated road damage detection, severity scoring, road health indexing, and maintenance prioritisation using computer vision and analytical modelling.

---

## Problem Statement

Road surface degradation causes billions of dollars in vehicle damage annually and poses significant public-safety hazards. Manual road inspections are slow, costly, and subjective. RoadGuard automates defect identification, severity assessment, and repair queue prioritization through transparent computer vision and analytical scoring.

---

## Solution Overview

RoadGuard integrates:
- **Computer Vision** — Bounding-box detection of 4 road damage taxonomy classes using fine-tuned YOLOv8.
- **Severity Engine** — Transparent analytical scoring derived from class weights, bounding-box spatial coverage, and confidence metrics.
- **Road Health Index (RHI)** — A standardized 0–100 condition metric for evaluated road segments.
- **Maintenance Priority Engine** — Explainable urgency scoring to rank repair queues.
- **GPS / EXIF Metadata Service** — Automatic geocoding and coordinate extraction from uploaded image EXIF headers.
- **FastAPI Production Backend** — Asynchronous REST API with automated OpenAPI schema documentation and CORS controls.
- **React + TypeScript Frontend** — Professional dark-mode intelligence dashboard with interactive charts, maps, and detection bounding-box visualization.

---

## Architecture

```
Browser (React + TypeScript)
         │  HTTP / REST API
         ▼
FastAPI Backend Application (Port 8001)
  ├── POST /api/detect       ← YOLO inference + analytical pipeline
  ├── GET  /api/health       ← System liveness & model readiness
  ├── GET  /api/inspections  ← Inspection records history
  ├── GET  /api/analytics/summary ← Aggregate metrics & KPIs
  ├── POST /api/maintenance/priority ← On-demand priority scoring
  └── GET  /api/maintenance/queue    ← Ranked repair dispatch queue
         │
         ├── services/detector.py    ← Ultralytics YOLO inference wrapper
         ├── services/severity.py    ← Analytical Severity Engine
         ├── services/scoring.py     ← Road Health Index calculator
         ├── services/optimizer.py   ← Priority ranking algorithm
         ├── services/gps.py         ← EXIF GPS parser & reverse geocoding
         └── services/inspection.py  ← SQLite persistence layer
         │
         └── models/road_damage.pt   ← YOLOv8-small fine-tuned weights (Git LFS)
```

---

## Model Setup & Git LFS

The trained YOLO model checkpoint is tracked using **Git Large File Storage (Git LFS)**.

* **Model File Path:** `models/road_damage.pt` (~85.4 MB)
* **Architecture:** `YOLOv8-small` (`ultralytics.nn.tasks.DetectionModel`)
* **Taxonomy Classes (RDD2020):**
  1. `Longitudinal Crack` (D00)
  2. `Transverse Crack` (D10)
  3. `Alligator Crack` (D20)
  4. `Potholes` (D40)

### Cloning & Pulling Weights
To obtain the model weights on a clean machine:

```bash
# Install Git LFS hooks
git lfs install

# Clone repository and pull LFS objects
git clone https://github.com/ShankhadeepM08/Road-Damage-Detection-YOLOv5.git
cd Road-Damage-Detection-YOLOv5
git lfs pull
```

---

## Environment Configuration

Configuration templates are provided in `.env.example` files.

### 1. Backend (`roadguard/backend/.env.example`)
* `CORS_ORIGINS`: Comma-separated list of allowed web frontend origins.
  ```env
  CORS_ORIGINS=http://localhost:5173,http://localhost:5174,http://localhost:3000
  ```

### 2. Frontend (`roadguard/frontend/.env.example`)
* `VITE_API_BASE_URL`: Base URL endpoint for FastAPI backend services.
  ```env
  VITE_API_BASE_URL=http://localhost:8001/api
  ```

---

## Local Setup & Quickstart

### Prerequisites
- Python 3.11+
- Node.js 18+
- Git LFS

### 1. Backend Setup

```bash
# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux

# Install backend dependencies
pip install -r requirements.txt

# Start FastAPI application
uvicorn roadguard.backend.app.main:app --host 0.0.0.0 --port 8001 --reload
```

* **Interactive API Documentation (Swagger UI):** `http://localhost:8001/api/docs`
* **ReDoc Specifications:** `http://localhost:8001/api/redoc`

### 2. Frontend Setup

```bash
cd roadguard/frontend
npm install
npm run dev
```

Open dashboard in browser: `http://localhost:5173`

---

## REST API Specifications

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Service liveness check & YOLO model readiness |
| `POST` | `/api/detect` | Process image upload, run YOLO, compute scores, persist record |
| `GET` | `/api/inspections` | Retrieve all historical inspection records (newest first) |
| `GET` | `/api/inspections/{id}` | Retrieve single inspection record by UUID |
| `GET` | `/api/analytics/summary` | Aggregate KPIs, class distributions, and health averages |
| `POST` | `/api/maintenance/priority` | Compute repair priority on custom parameter inputs |
| `GET` | `/api/maintenance/queue` | Ranked maintenance queue sorted by urgency score |

---

## Verification & Testing

### Backend Unit Test Suite (pytest)
Runs 23 automated unit tests validating analytical engines, EXIF parsers, model availability, and API endpoints:

```bash
.venv\Scripts\pytest.exe
```

### Standalone Model Verification
Verifies model deserialization and inference pipeline against test image:

```bash
.venv\Scripts\python scripts/test_inference.py
```

### Frontend Build Verification
Validates TypeScript compilation and Vite production bundling:

```bash
cd roadguard/frontend
npm run build
```

---

## Current Release Status vs. Roadmap

### Currently Implemented (RoadGuard v1.0)
- ✅ **YOLOv8 Object Detection** — Fine-tuned detection on road defects.
- ✅ **Severity Engine** — Analytical spatial & confidence scoring.
- ✅ **Road Health Index (RHI)** — Standardized surface condition rating.
- ✅ **EXIF / GPS Extraction** — Dual-path PIL/piexif coordinate extraction & geocoding.
- ✅ **SQLite Persistence** — Inspection record schema auto-initialization.
- ✅ **Maintenance Priority Engine** — Multi-factor urgency ranking.
- ✅ **React Dashboard** — Dark-mode interface with live charts and map visualizers.
- ✅ **Production Readiness** — Git LFS model tracking, environment variable configuration, clean repository architecture.

### Upcoming Planned Extensions
- 🔮 **Phase 11: Video Stream Analytics** — Real-time continuous dashcam stream processing & spatial defect deduplication.
- 🔮 **Phase 12: Machine Learning Deterioration Modeling** — Predictive degradation modeling using XGBoost.
- 🔮 **Phase 13: Maintenance Route Optimization** — Operational repair dispatch routing using Google OR-Tools.