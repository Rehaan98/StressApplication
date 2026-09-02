# 🧠 Psychological Stress AI — Full-Stack Multi-Modal Explainable AI Platform

![Build Status](https://img.shields.io/badge/build-passing-brightgreen)
![Python Version](https://img.shields.io/badge/python-3.11+-blue)
![Next.js](https://img.shields.io/badge/next.js-14.2-black)
![License](https://img.shields.io/badge/license-MIT-purple)

> An enterprise-grade, multi-modal psychological stress assessment and explainable AI platform. Combines psychometric scoring (PSS-10), physiological telemetry (HRV, Heart Rate), **real-time webcam facial expression recognition (FER2013 CNN)**, sleep & lifestyle tracking, ML predictions (XGBoost/GradientBoosting), SHAP & LIME transparency, and RAG-driven clinical coping interventions.

---

## 🌟 Key Features

- **📷 Real-Time Facial Expression Stress Scan**: Webcam-based emotion recognition powered by a CNN trained on the **FER2013 dataset** (ONNX Runtime, 8 FER+ classes). Detects anger, fear, sadness, surprise, disgust, contempt, neutral and happiness every 2.5s and maps them to a continuous 0–100 stress score. Includes live emotion probability bars, session trend chart, and privacy-first frame handling (frames are never stored as images).
- **💡 Emotion-Aware RAG**: The Retrieval-Augmented Generation engine matches the *detected facial emotion* — not just questionnaire drivers — to tailored CBT protocols, anger cool-downs, fear grounding, sadness behavioural activation, and savoring techniques.
- **📊 Multi-Modal Stress Assessment**: Combines PSS-10 perceived stress questionnaire (with server-side reverse scoring), physiological metrics (HRV SDNN, heart rate), sleep efficiency, workload indicators, and facial-expression readings.
- **🤖 Explainable ML Engine (XAI)**:
  - **SHAP (SHapley Additive exPlanations)**: Waterfall and bar charts quantifying per-feature contribution to stress risk.
  - **LIME Decision Rules**: Local surrogate if-then rules explaining instance-level model logic in plain language.
  - **Global Feature Importance**: Population-wide driver breakdown across trained gradient boosted decision trees.
- **📈 Interactive Analytics & Export**: Multi-dimensional trend charts (PSS, HRV, sleep, stress distribution, facial stress) and automated CSV report export.
- **🔒 RBAC & Security**: JWT Authentication, bcrypt password hashing (with legacy-scheme compatibility), role-based access control (Admin, Clinician, User), and complete system audit logging.
- **🎨 Glassmorphic Modern UI**: Dark-mode primary Next.js 14 frontend built with TailwindCSS, Lucide icons, Framer Motion, and Recharts.

---

## 📁 Repository Structure

```
Psychological stress AI/
├── backend/                  # FastAPI Asynchronous REST API
│   ├── app/
│   │   ├── api/v1/endpoints/ # Auth, Assessments, Predictions, XAI, RAG, Analytics, Admin
│   │   ├── core/             # Config, Security, DB session
│   │   ├── models/           # SQLAlchemy Async ORM models
│   │   ├── schemas/          # Pydantic v2 request/response schemas
│   │   └── services/         # Business logic & ML integration services
│   ├── requirements.txt      # Python dependencies
│   └── Dockerfile
├── frontend/                 # Next.js 14 App Router Web Application
│   ├── src/
│   │   ├── app/              # Dashboard, Assessment, Explainability, RAG, Analytics, Admin, Settings
│   │   ├── components/       # Glassmorphism UI components, Recharts visualizations
│   │   └── lib/              # Axios API client, authentication helpers
│   ├── package.json
│   └── Dockerfile
├── ml_engine/                # Machine Learning & Explainable AI Core
│   ├── data/                 # Synthetic dataset generator & clinical knowledge base
│   └── src/                  # Feature engineering, Preprocessor, Trainer, Evaluator, XAI, RAG
├── database/                 # DDL init.sql & async python database seeder
├── tests/                    # Backend API integration tests & ML pipeline unit tests
├── docker-compose.yml        # Multi-container orchestration (PostgreSQL + FastAPI + Next.js)
├── pytest.ini
└── README.md
```

---

## 🚀 Quick Start Guide

### Prerequisites
- **Python 3.11+**
- **Node.js 18+ / npm 9+**
- **Docker & Docker Compose** *(optional, for containerized run)*

---

### Option 1: Local Development Setup

#### 1. Backend Setup
```bash
# Navigate to project root
cd "Psychological stress AI"

# Create & activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install -r backend/requirements.txt

# (Recommended) Verify/download facial expression recognition artifacts
python -c "from ml_engine.facial.fer_detector import FacialStressAnalyzer; FacialStressAnalyzer(download_if_missing=True)"

# Train ML Models & build RAG vector index
python -m ml_engine.src.train_pipeline

# Seed SQLite development database
python database/seed_data.py

# Start FastAPI dev server
uvicorn backend.app.main:app --reload --port 8000
```
Backend API will be live at: **`http://localhost:8000`**  
Interactive OpenAPI Docs: **`http://localhost:8000/docs`**

#### 2. Frontend Setup
```bash
# In a new terminal window:
cd "Psychological stress AI/frontend"

# Install npm dependencies
npm install

# Start Next.js development server
npm run dev
```
Web Application will be live at: **`http://localhost:3000`**

> 💡 **Webcam Feature**: Open the **Facial Stress Scan** page (sidebar → "Facial Stress Scan") and allow camera access. The FER2013 CNN analyzes your expression every 2.5 seconds, shows live emotion probabilities and a stress score, and retrieves emotion-tailored RAG coping interventions. Your video never leaves the browser — only small anonymized frames are transmitted for inference and never stored as images.

### Production / Large-Scale Serving
```bash
# Backend with 4 worker processes (scales horizontally; tune via STRESSAI_WORKERS)
STRESSAI_WORKERS=8 ./start.sh backend-prod

# Facial recognition artifacts auto-verified at startup:
./start.sh facial
```

Facial inference runs off the event loop (`asyncio.to_thread`) on a shared singleton ONNX session; every analysis is stateless, so the service scales horizontally behind any load balancer. Inference cost is bounded by downsampling frames to ≤640px (~65–100ms per frame on CPU).

---

### Option 2: Docker Compose Setup

Run the full stack (PostgreSQL + FastAPI + Next.js) in containerized mode:

```bash
docker-compose up --build
```
- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8000`
- PostgreSQL: `localhost:5432`

---

## 🧪 Running Tests

Run the full test suite (API integration + ML pipeline unit tests):

```bash
# Ensure virtual environment is active
pytest
```

To run specific test modules:
```bash
# ML Pipeline Unit Tests
pytest tests/ml/test_ml_pipeline.py

# Backend Auth Integration Tests
pytest tests/backend/test_auth.py

# Assessment Endpoint Tests
pytest tests/backend/test_assessments.py

# RAG Intervention Tests
pytest tests/backend/test_rag.py

# Facial Expression Analysis Tests
pytest tests/backend/test_facial.py
```

---

## 🔑 Demo Account Credentials

Default pre-seeded accounts available for testing:

| Role | Email | Password |
|---|---|---|
| **Admin** | `admin@stressai.com` | `Admin@StressAI2026` |
| **Clinician** | `dr.sarah@clinic.com` | `Clinician@2026` |
| **User** | `user@stressai.com` | `User@2026` |

---

## 🔬 Machine Learning Model Summary

| Model | Dataset | Metric | Value |
|---|---|---|---|
| Stress Classifier (XGBoost/GradientBoosting) | Synthetic stress (3000 samples, 4 classes) | Accuracy | **86.3%** |
|  |  | F1-Score (Macro) | **84.5%** |
|  |  | ROC-AUC | **97.4%** |
| **Facial Expression (emotion-ferplus-8)** | **FER2013** (48×48 grayscale, 7 classes + contempt) | Classes | 8 emotions |
|  |  | Inference | ~65–100ms/frame CPU |

---

## 🗂️ RAG Knowledge Base

The retrieval engine (`ml_engine/rag/rag_knowledge_base.json`) contains 12 evidence-based intervention protocols across CBT, autonomic regulation, sleep hygiene, workload ergonomics, somatic release, and emotion-specific plans (anger, fear, sadness, surprise, disgust, happiness). Every intervention is tagged with `target_drivers`, `target_emotions` and `stress_levels` so retrieval is boosted for both SHAP-identified drivers and the user's live facial expression.

---

## 📜 License

This project is released under the **MIT License**.
