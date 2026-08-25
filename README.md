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

### Currently Implemented (RoadGuard v1.1)
- [x] YOLOv8 Object Detection - Fine-tuned detection on road defects.
- [x] Severity Engine - Analytical spatial & confidence scoring.
- [x] Road Health Index (RHI) - Standardized surface condition rating.
- [x] EXIF / GPS Extraction - Dual-path PIL/piexif coordinate extraction & geocoding.
- [x] SQLite Persistence - Inspection record schema auto-initialization.
- [x] Maintenance Priority Engine - Multi-factor urgency ranking.
- [x] React Dashboard - Dark-mode interface with live charts and map visualizers.
- [x] Video Road Inspection (Phase 11) - Frame sampling, temporal deduplication, and aggregation.
- [x] Predictive Road Deterioration (Phase 12) - Machine learning deterioration modeling using XGBoost.
- [ ] Phase 13: Maintenance Route Optimization - Operational repair dispatch routing using Google OR-Tools.

---

## Predictive Road Deterioration

### Business Problem
Managing road infrastructure requires proactive maintenance. By predicting the likelihood that a road segment will deteriorate into a high-priority maintenance case, municipal authorities can optimize budget allocation and prevent severe road failures.

### Target Definition
- Classifier Target (high_priority_next_period): Binary target set to 1 if the road priority score at the next inspection period is >= 65, else 0.
- Regressor Target (future_road_health): Continuous target representing the road health score in the next inspection period.

### Features
The predictive analytics service utilizes the following historical inspection attributes:
- Current Road Health Index, severity score, priority score, and defect count
- Counts of individual defect classes (D00, D10, D20, D40)
- Average confidence and maximum defect severity score
- Video-specific indicators (damage frame percentage and unique deduplicated detections)
- Number of previous inspections, days since last inspection, and daily deterioration rate

All features represent information available strictly before the prediction horizon to prevent target leakage.

### Architecture Explanation
```
Historical inspections
↓
Feature engineering
↓
Temporal dataset
↓
XGBoost deterioration model
↓
Risk probability
↓
Explainable prediction
↓
Maintenance decision support
```

### XGBoost Model & Chronological Split
The classification model is built using XGBoost (XGBClassifier) with a fixed seed (random_state=42) for reproducibility. To prevent temporal leakage, train/validation splitting is performed chronologically (80% training, 20% validation).

### Evaluation Metrics
Validation metrics computed on the synthetic prototype dataset:
- ROC-AUC: Area under the ROC curve for classification risk.
- PR-AUC: Area under the Precision-Recall curve.
- Precision, Recall, and F1 Score for high-priority classification.
- Mean Absolute Error (MAE) and Root Mean Squared Error (RMSE) for future health regression.

### Synthetic Data Limitation
As the database starts without historical longitudinal inspection sequences, a deterministic generator (scripts/generate_prediction_dataset.py) is used to create prototype histories. These validation metrics must be interpreted as prototype-only until actual longitudinal data is gathered.

### APIs
- POST /api/predictions/deterioration : Run inference on segment payload and persist results.
- GET /api/predictions/model : Retrieve model metadata, metrics, and training configuration.
- GET /api/predictions/risk-summary : Retrieve aggregated risk categories across segments.
- POST /api/predictions/train : Retrain the classification and regression models.

### Training and Execution
To retrain the models manually, run:
```bash
.venv\Scripts\python -c "from roadguard.backend.app.services.prediction import train_and_save_pipeline, load_raw_dataset; train_and_save_pipeline(load_raw_dataset())"
```