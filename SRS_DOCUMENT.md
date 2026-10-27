# Software Requirements Specification (SRS)
## Psychological Stress AI Platform

---

## 1. Introduction

### 1.1 Purpose
This Software Requirements Specification (SRS) document describes the functional and non-functional requirements for the **Psychological Stress AI** platform, a full-stack multi-modal explainable AI system for psychological stress assessment, prediction, and evidence-based coping intervention recommendations.

### 1.2 Scope
This document covers all system components including the web frontend, backend API, machine learning pipeline, explainable AI (XAI) engine, Retrieval-Augmented Generation (RAG) coping engine, facial expression recognition, authentication and authorization, and database management. It serves as the baseline for development, testing, and deployment.

### 1.3 Document Conventions
- **Shall**: Mandatory requirement
- **Should**: Target goal
- **May**: Optional capability
- **Must Not**: Prohibited action

### 1.4 References
- ARCHITECTURE.md - System architecture and technical specifications
- SYSTEM_ARCHITECTURE_GUIDE.md - Technical reference and workflow guide
- README.md - User documentation and quick start guide
- backend/requirements.txt - Python dependencies
- frontend/package.json - Node.js dependencies

---

## 2. Overall Description

### 2.1 Product Perspective
Psychological Stress AI is a standalone full-stack application consisting of:
- **Frontend**: Next.js 14 App Router web interface (port 3000)
- **Backend**: FastAPI asynchronous REST API (port 8000)
- **ML Engine**: Python-based model training, prediction, and explainability
- **RAG Engine**: TF-IDF knowledge base for coping interventions
- **Facial Analysis**: Webcam-based emotion recognition using ONNX FER2013 CNN
- **Database**: SQLite for local development, PostgreSQL for production

The system follows a client-server architecture where the frontend communicates with the backend via RESTful JSON endpoints authenticated with JWT bearer tokens.

### 2.2 Product Functions
The system provides the following core functions:

| Function ID | Function Description |
|---|---|
| **F-001** | User registration and authentication with JWT-based authorization |
| **F-002** | PSS-10 psychometric questionnaire submission with server-side reverse scoring |
| **F-003** | Multi-modal stress assessment using physiological, lifestyle, and cognitive inputs |
| **F-004** | ML model prediction of stress level (Low/Moderate/High/Severe) |
| **F-005** | SHAP-based feature attribution explaining predictions |
| **F-006** | LIME local surrogate model generating if-then decision rules |
| **F-007** | Retrieval-Augmented Generation (RAG) coping intervention recommendations |
| **F-008** | Real-time facial expression recognition and stress scoring |
| **F-009** | Analytics dashboard with trend charts and CSV report export |
| **F-010** | Role-based access control (RBAC): User, Clinician, Admin |
| **F-011** | Audit logging of authentication events, predictions, and RAG queries |
| **F-012** | Seed data initialization for demo accounts |

### 2.3 User Classes and Characteristics
| Role | Characteristics | Permissions |
|---|---|---|
| **user** | Registered account holder | Submit self-assessments, view personal predictions and coping strategies |
| **clinician** | Healthcare professional | View patient assessments, trend analytics, detailed SHAP/LIME breakdown |
| **admin** | System administrator | User administration, model monitoring, audit log oversight |

### 2.4 Operating Environment
- **Frontend**: Modern web browser (Chrome, Firefox, Safari, Edge) with webcam access for facial recognition
- **Backend**: Python 3.11+, FastAPI, uvicorn
- **ML Dependencies**: XGBoost, SHAP, LIME, scikit-learn, pandas, numpy
- **RAG**: TF-IDF vectorizer, JSON knowledge base
- **Facial Recognition**: ONNX Runtime, FER2013 model
- **Database**: SQLite (local dev), PostgreSQL (production/containers)
- **Deployment**: Local development, Docker Compose, production containers

### 2.5 Constraints
- Must use HTTPS for all external communication
- Passwords must be hashed with bcrypt (minimum 12 work factor)
- JWT tokens have 7-day expiry (10080 minutes)
- Webcam frames must not be stored; only anonymized data transmitted
- System must operate within HIPAA-compliant data handling guidelines

### 2.6 Assumptions and Dependencies
- Users have access to a webcam for facial expression analysis (optional feature)
- ML model artifacts are pre-trained and available
- Database is properly initialized and accessible
- Environment variables (.env) are configured correctly

---

## 3. Functional Requirements

### 3.1 Authentication & Authorization

| Requirement ID | Requirement |
|---|---|
| **FR-AUTH-001** | The system shall support user registration with email, full name, and password |
| **FR-AUTH-002** | The system shall support user login with JWT token generation (HS256 signing) |
| **FR-AUTH-003** | Passwords shall be hashed using bcrypt with 12 work factor rounds |
| **FR-AUTH-004** | Access tokens shall have 7-day expiry (10080 minutes) |
| **FR-AUTH-005** | Role-based access control shall enforce: user (own data), clinician (patient data), admin (all data) |
| **FR-AUTH-006** | The system shall validate bearer tokens on protected routes via `get_current_user` |
| **FR-AUTH-007** | The system shall maintain audit logs of all auth events, predictions, and RAG queries |

### 3.2 Assessment & Prediction

| Requirement ID | Requirement |
|---|---|
| **FR-ASS-001** | The system shall accept PSS-10 questionnaire responses (10 items, 0-4 scale each) |
| **FR-ASS-002** | The system shall perform server-side reverse scoring on PSS-10 items 4, 5, 7, 8 |
| **FR-ASS-003** | The system shall collect physiological inputs: heart_rate (BPM), hrv_sdnn (ms), sleep_hours, sleep_efficiency (%), physical_activity_min (min/day) |
| **FR-ASS-004** | The system shall collect workload/cognitive inputs: work_hours (hrs/day), screen_time_hours (hrs/day), breaks_per_day (count), sentiment_score (-1.0 to +1.0), anxiety_score (0-10) |
| **FR-ASS-005** | The system shall engineer 5 derived features: hrv_to_hr_ratio, sleep_deficiency_index, work_stress_factor, composite_strain_index |
| **FR-ASS-006** | The system shall use a trained GradientBoosting classifier (best of 3 via stratified K-Fold CV) for stress prediction |
| **FR-ASS-007** | The system shall predict stress level: 0=Low, 1=Moderate, 2=High, 3=Severe |
| **FR-ASS-008** | The system shall provide confidence_score and class_probabilities for each prediction |
| **FR-ASS-009** | The system shall achieve minimum macro F1-score of 85% on test data |

### 3.3 Explainable AI (XAI)

| Requirement ID | Requirement |
|---|---|
| **FR-XAI-001** | The system shall generate SHAP values per feature for model attribution |
| **FR-XAI-002** | The system shall identify top-7 SHAP stress drivers (amplifiers and protective buffers) |
| **FR-XAI-003** | The system shall generate LIME local surrogate model with if-then decision rules |
| **FR-XAI-004** | The system shall present SHAP waterfall and bar charts in the UI |
| **FR-XAI-005** | The system shall present LIME impact lists explaining instance-level predictions |
| **FR-XAI-006** | SHAP and LIME explanations shall be persisted in `explainability_logs` table |

### 3.4 Retrieval-Augmented Generation (RAG) Coping Engine

| Requirement ID | Requirement |
|---|---|
| **FR-RAG-001** | The system shall build a query combining stress level, top SHAP drivers, and user free-text |
| **FR-RAG-002** | The system shall use TF-IDF vectorizer trained on 6 intervention documents |
| **FR-RAG-003** | The system shall compute cosine similarity between query and knowledge base documents |
| **FR-RAG-004** | The system shall apply domain boost: +0.25 per SHAP driver matching intervention `target_drivers` |
| **FR-RAG-005** | The system shall return top-3 interventions with `relevance_score` |
| **FR-RAG-006** | RAG queries shall be logged to `rag_coping_logs` table |
| **FR-RAG-007** | The knowledge base contains 6 evidence-based intervention categories: Autonomic Nervous System Regulation, CBT, Mindfulness & Affective Regulation, Physical Activity & Somatic Discharge, Sleep Hygiene & Recovery, Workload & Screen Ergonomics |

### 3.5 Facial Expression Recognition

| Requirement ID | Requirement |
|---|---|
| **FR-FAC-001** | The system shall support webcam-based facial expression recognition |
| **FR-FAC-002** | The system shall use FER2013 CNN model (8 classes: anger, fear, sadness, surprise, disgust, contempt, neutral, happiness) |
| **FR-FAC-003** | The system shall analyze frames every 2.5 seconds |
| **FR-FAC-004** | The system shall produce live emotion probability bars and continuous 0-100 stress score |
| **FR-FAC-005** | The system shall map detected emotions to tailored RAG coping interventions |
| **FR-FAC-006** | The system shall not store facial frames as images (privacy-first) |
| **FR-FAC-007** | The system shall use `asyncio.to_thread` for offloading inference to shared ONNX session |

### 3.6 Analytics & Reporting

| Requirement ID | Requirement |
|---|---|
| **FR-ANA-001** | The system shall provide user analytics dashboard with multi-dimensional trend charts |
| **FR-ANA-002** | The system shall support charts for: PSS scores, HRV, sleep metrics, stress distribution, facial stress trends |
| **FR-ANA-003** | The system shall provide CSV report export of assessment and prediction data |
| **FR-ANA-004** | The system shall support admin analytics: system-wide user metrics, model performance monitoring |

### 3.7 Database & Data Management

| Requirement ID | Requirement |
|---|---|
| **FR-DB-001** | The system shall use SQLite for local development (`stress_ai.db`) |
| **FR-DB-002** | The system shall support PostgreSQL for production deployments |
| **FR-DB-003** | The database shall consist of 6 tables: users, stress_assessments, predictions, explainability_logs, rag_coping_logs, audit_logs |
| **FR-DB-004** | The system shall seed 3 demo accounts: user@stressai.com, admin@stressai.com, dr.sarah@clinic.com |
| **FR-DB-005** | All predictions, explanations, and retrievals must be persisted for end-to-end auditability |

---

## 4. Non-Functional Requirements

### 4.1 Performance Requirements
| Requirement ID | Requirement |
|---|---|
| **NF-PERF-001** | ML prediction inference shall complete within 100ms per request |
| **NF-PERF-002** | Facial expression analysis shall process frames in 65-100ms on CPU |
| **NF-PERF-003** | API response time shall be < 500ms for 95th percentile of requests |
| **NF-PERF-004** | TF-IDF cosine similarity search shall complete within 50ms |
| **NF-PERF-005** | CSV report generation shall complete within 2 seconds |

### 4.2 Security Requirements
| Requirement ID | Requirement |
|---|---|
| **NF-SEC-001** | All communication shall use HTTPS/TLS encryption |
| **NF-SEC-002** | Passwords shall be stored using bcrypt with 12 work factor rounds |
| **NF-SEC-003** | JWT tokens shall be signed using HMAC-SHA256 (HS256) |
| **NF-SEC-004** | Access tokens shall have 7-day expiry with refresh mechanism |
| **NF-SEC-005** | Role-based access control shall prevent unauthorized data access |
| **NF-SEC-006** | All auth events, predictions, and RAG queries shall be logged to audit_logs |
| **NF-SEC-007** | System shall not store webcam frames as images; privacy-first design |

### 4.3 Reliability Requirements
| Requirement ID | Requirement |
|---|---|
| **NF-REL-001** | System shall achieve 99.9% uptime for API endpoints |
| **NF-REL-002** | ML model artifacts shall be loadable at startup without errors |
| **NF-REL-003** | Database migrations shall be backward-compatible |
| **NF-REL-004** | System shall gracefully handle missing or invalid input data |

### 4.4 Maintainability Requirements
| Requirement ID | Requirement |
|---|---|
| **NF-MAINT-001** | Codebase shall follow existing directory structure: backend/app/{core,models,schemas,services}, frontend/src/{app,components,lib} |
| **NF-MAINT-002** | ML model retraining script shall be available (`./start.sh train`) |
| **NF-MAINT-003** | Database seeding script shall be available (`database/seed_data.py`) |
| **NF-MAINT-004** | Documentation shall be kept in sync with code changes |

### 4.5 Scalability Requirements
| Requirement ID | Requirement |
|---|---|
| **NF-SCAL-001** | Backend shall support horizontal scaling via multiple worker processes (`STRESSAI_WORKERS` env var) |
| **NF-SCAL-002** | Facial inference is stateless and scales horizontally behind load balancer |
| **NF-SCAL-003** | PostgreSQL backend supported for production containerized deployment |

### 4.6 Compliance Requirements
| Requirement ID | Requirement |
|---|---|
| **NF-COMP-001** | System shall follow HIPAA-compliant data handling for psychological data |
| **NF-COMP-002** | Audit logs shall maintain append-only trail of all system events |
| **NF-COMP-003** | User consent required before facial analysis processing |

---

## 5. Interface Requirements

### 5.1 User Interfaces
| Interface ID | Description |
|---|---|
| **UI-001** | Next.js 14 web application with App Router |
| **UI-002** | Dashboard page: overview of assessments, trends, gauges |
| **UI-003** | Assessment wizard: 4-step form (PSS-10, physiological, workload, review) |
| **UI-004** | Predictions page: stress level display, confidence score, class probabilities |
| **UI-005** | XAI/Explainability page: SHAP bar charts, LIME decision rules |
| **UI-006** | RAG Coping page: top-3 interventions with relevance scores |
| **UI-007** | Facial Stress Scan page: live webcam feed, emotion probabilities, stress score |
| **UI-008** | Analytics page: multi-dimensional trend charts (Recharts) |
| **UI-009** | Admin panel: user management, system analytics, audit log oversight |
| **UI-010** | Settings page: account management, dark mode toggle |

### 5.2 API Interfaces
| Interface ID | Description |
|---|---|
| **API-001** | RESTful JSON endpoints on FastAPI (port 8000) |
| **API-002** | Authentication endpoints: POST /auth/login, POST /auth/register, GET /auth/me |
| **API-003** | Assessment endpoints: POST /assessments/, GET /assessments/, GET /assessments/{id} |
| **API-004** | Prediction endpoints: POST /predictions/, GET /predictions/, GET /predictions/{id} |
| **API-005** | XAI endpoints: GET /explainability/{pred_id} |
| **API-006** | RAG endpoints: POST /rag/ |
| **API-007** | Analytics endpoints: GET /analytics/user, GET /analytics/admin |
| **API-008** | Admin endpoints: GET/POST /admin/users, GET /admin/analytics |
| **API-009** | Reports endpoint: GET /reports/csv |
| **API-010** | Facial endpoints: POST /facial/scan, GET /facial/status |
| **API-011** | Tracker endpoints: POST /tracker/data, GET /tracker/history |

### 5.3 Hardware Interfaces
| Interface ID | Description |
|---|---|
| **HW-001** | Webcam access for facial expression recognition (optional feature) |
| **HW-002** | Standard display monitor (minimum 1280×720 resolution) |
| **HW-003** | Input devices: keyboard, mouse/touchpad |

### 5.4 Software Interfaces
| Interface ID | Description |
|---|---|
| **SW-001** | Next.js 14 frontend communicating with FastAPI backend via REST JSON |
| **SW-002** | Axios HTTP client with JWT interceptor (frontend → backend) |
| **SW-003** | ONNX Runtime for facial expression model inference |
| **SW-004** | SQLAlchemy async ORM for database operations |
| **SW-005** | bcrypt for password hashing |
| **SW-006** | JWT Python library for token generation/validation |

---

## 6. Data Requirements

### 6.1 Database Schema

#### 6.1.1 users Table
| Column | Type | Constraints | Description |
|---|---|---|---|
| id | INTEGER | PK, auto-increment | Unique identifier |
| email | VARCHAR(255) | UNIQUE, NOT NULL | User email address |
| full_name | VARCHAR(255) | NOT NULL | User's full name |
| hashed_password | VARCHAR(255) | NOT NULL | bcrypt hash |
| role | VARCHAR(50) | NOT NULL, DEFAULT 'user' | RBAC role (user/clinician/admin) |
| is_active | BOOLEAN | NOT NULL, DEFAULT True | Account status |
| is_verified | BOOLEAN | NOT NULL, DEFAULT False | Email verification status |

#### 6.1.2 stress_assessments Table
| Column | Type | Constraints | Description |
|---|---|---|---|
| id | INTEGER | PK, auto-increment | Unique identifier |
| user_id | INTEGER | FK → users.id, NOT NULL | Owner of assessment |
| pss_q1 through pss_q10 | INTEGER | NOT NULL (0-4) | PSS-10 item responses |
| total_pss | INTEGER | NOT NULL (0-40) | Reverse-scored total |
| heart_rate | INTEGER | BPM (50-120) | Physiological metric |
| hrv_sdnn | INTEGER | ms (15-120) | HRV SDNN metric |
| sleep_hours | REAL | Hours per night | Lifestyle metric |
| sleep_efficiency | INTEGER | Percentage (%) | Sleep efficiency |
| physical_activity_min | INTEGER | Minutes per day | Lifestyle metric |
| work_hours | REAL | Hours per day | Workload metric |
| screen_time_hours | REAL | Hours per day | Workload metric |
| breaks_per_day | INTEGER | Count | Workload metric |
| sentiment_score | REAL | -1.0 to +1.0 | VADER text sentiment |
| anxiety_score | INTEGER | 0-10 scale | Anxiety rating |
| notes | TEXT | Optional | Free-form notes |

#### 6.1.3 predictions Table
| Column | Type | Constraints | Description |
|---|---|---|---|
| id | INTEGER | PK, auto-increment | Unique identifier |
| user_id | INTEGER | FK → users.id, NOT NULL | Associated user |
| assessment_id | INTEGER | FK → stress_assessments.id, NOT NULL | Source assessment |
| predicted_class_id | INTEGER | NOT NULL (0-3) | Predicted stress class |
| stress_level | VARCHAR(20) | NOT NULL (Low/Moderate/High/Severe) | Human-readable label |
| confidence_score | REAL | 0.0-1.0 | Prediction confidence |
| class_probabilities | JSON | NOT NULL | Per-class probabilities |
| created_at | DATETIME | NOT NULL | Timestamp |

#### 6.1.4 explainability_logs Table
| Column | Type | Constraints | Description |
|---|---|---|---|
| id | INTEGER | PK, auto-increment | Unique identifier |
| prediction_id | INTEGER | FK → predictions.id, NOT NULL | Associated prediction |
| shap_top_drivers | JSON | NOT NULL | Top SHAP feature attributions |
| lime_rules | JSON | NOT NULL | LIME if-then decision rules |
| created_at | DATETIME | NOT NULL | Timestamp |

#### 6.1.5 rag_coping_logs Table
| Column | Type | Constraints | Description |
|---|---|---|---|
| id | INTEGER | PK, auto-increment | Unique identifier |
| user_id | INTEGER | FK → users.id, NOT NULL | Requesting user |
| prediction_id | INTEGER | FK → predictions.id | Associated prediction (optional) |
| query_text | TEXT | NOT NULL | Original user query |
| retrieved_interventions | JSON | NOT NULL | Top-3 interventions with scores |
| relevance_scores | JSON | NOT NULL | Per-intervention relevance scores |
| created_at | DATETIME | NOT NULL | Timestamp |

#### 6.1.6 audit_logs Table
| Column | Type | Constraints | Description |
|---|---|---|---|
| id | INTEGER | PK, auto-increment | Unique identifier |
| user_id | INTEGER | FK → users.id | User who triggered action (optional) |
| action | VARCHAR(100) | NOT NULL | Action performed |
| ip_address | VARCHAR(45) | NOT NULL | Source IP address |
| details | JSON | NOT NULL | Additional context |
| created_at | DATETIME | NOT NULL | Timestamp |

### 6.2 ML Model Artifacts
| Artifact | File | Contents |
|---|---|---|
| Trained model | `ml_engine/models/stress_model.joblib` | Best gradient boosting classifier + CV results |
| Preprocessor | `ml_engine/models/preprocessor.joblib` | Fitted median imputer + RobustScaler (25-dim feature space) |
| RAG engine | `ml_engine/models/rag_engine.joblib` | Knowledge base + fitted TF-IDF vectorizer |
| Evaluation metrics | `ml_engine/models/eval_metrics.json` | Accuracy, F1, precision, recall, ROC-AUC |

### 6.3 RAG Knowledge Base
| Field | Type | Description |
|---|---|---|
| id | INTEGER | Unique intervention identifier |
| category | VARCHAR(100) | Intervention category |
| title | VARCHAR(255) | Intervention title |
| summary | TEXT | Brief description |
| protocol | TEXT | Step-by-step protocol |
| evidence_base | TEXT | Clinical evidence source |
| difficulty | VARCHAR(50) | Difficulty level (beginner/intermediate/advanced) |
| duration_min | INTEGER | Duration in minutes |
| target_drivers | JSON | SHAP feature names this intervention targets |
| target_emotions | JSON | Emotions this intervention addresses |
| stress_levels | JSON | Stress levels this intervention applies to |

### 6.4 Synthetic Training Dataset
| Property | Value |
|---|---|
| Records | 3,000 samples |
| Features | 22-dimensional feature space (10 PSS items + total_pss + physiological + workload + derived features) |
| Target | stress_level 0-3 (derived from weighted composite: PSS 40%, HRV 25%, sleep 20%, anxiety 15%) |
| Class distribution: >= 0.35 = Moderate, >= 0.58 = High, >= 0.78 = Severe |
| Train/test split: 80/20 stratified |
| Model quality (GradientBoosting): Accuracy 86.3%, Macro F1 84.5%, ROC-AUC 97.4% |

---

## 7. External Interface Requirements

### 7.1 Communications Interface
- All API communications use HTTPS with TLS 1.2+
- JWT tokens transmitted via HTTP Authorization Bearer header
- WebSocket not currently used (RESTful JSON only)

### 7.2 Data Exchange Format
- All endpoints exchange JSON format
- Error responses follow FastAPI HTTPException format
- CSV reports exported as comma-separated values

### 7.3 Error Handling
- 400: Bad request (validation errors, missing fields)
- 401: Unauthorized (invalid/missing JWT token)
- 403: Forbidden (insufficient permissions)
- 422: Unprocessable entity (validation failures)
- 500: Internal server error

### 7.4 Facial Recognition Interface
- Webcam stream accessed via `getUserMedia` API
- Frames transmitted to backend via base64-encoded JPEG
- Inference performed via ONNX Runtime with asyncio.to_thread
- No video/audio storage; only small anonymized frame data for inference

---

## 8. Design Constraints
- **Language**: Python 3.11+, TypeScript/React for frontend
- **Framework**: FastAPI for backend, Next.js 14 for frontend
- **Database**: SQLite for development, PostgreSQL for production
- **Authentication**: JWT (HS256) + bcrypt (12 rounds)
- **ML Libraries**: XGBoost, SHAP, LIME, scikit-learn, ONNX Runtime
- **Styling**: TailwindCSS, glassmorphic UI design
- **Deployment**: Docker Compose for containerized deployment

---

## 9. Appendices

### 9.1 Acronyms
| Acronym | Expansion |
|---|---|
| SRS | Software Requirements Specification |
| PSS-10 | Perceived Stress Scale-10 items |
| SHAP | SHapley Additive exPlanations |
| LIME | Local Interpretable Model-agnostic Explanations |
| RAG | Retrieval-Augmented Generation |
| TF-IDF | Term Frequency-Inverse Document Frequency |
| HRV | Heart Rate Variability |
| SDNN | Standard Deviation of NN intervals |
| XAI | Explainable AI |
| CBT | Cognitive Behavioral Therapy |
| FER2013 | Facial Expression Recognition 2013 dataset |
| CNN | Convolutional Neural Network |
| RBAC | Role-Based Access Control |
| API | Application Programming Interface |
| ML | Machine Learning |
| BMI | Body Mass Index (not used) |
| JWT | JSON Web Token |

### 9.2 Glossary
- **Stress Level**: Classification of stress severity (Low=0, Moderate=1, High=2, Severe=3)
- **SHAP Values**: Feature attribution scores representing marginal contribution to prediction
- **LIME Rules**: Local surrogate model if-then conditions explaining individual predictions
- **Composite Strain Index**: Weighted blend of PSS, anxiety, sentiment, and sleep deficit
- **Domain Boost**: TF-IDF relevance score adjustment based on SHAP driver matching

### 9.3 Version History
| Version | Date | Author | Changes |
|---|---|---|---|
| 1.0 | 2026-09-18 | System | Initial SRS document |

### 9.4 Change Log
- Initial document created based on project analysis of Psychological Stress AI platform
- Covers all functional and non-functional requirements across frontend, backend, ML pipeline, RAG engine, and facial analysis components

---

## 10. Use Case Diagrams

### 10.1 Overall System Use Case Diagram

```
useCaseDiagram
    title Psychological Stress AI - Use Case Diagram
    
    actor "User" as U
    actor "Clinician" as C
    actor "Admin" as A
    
    package "Authentication" {
        usecase "Register" <<register>>
        usecase "Login" <<login>>
        usecase "Logout" <<logout>>
    }
    
    package "Stress Assessment" {
        usecase "Submit PSS-10 Questionnaire" <<submit_assessment>>
        usecase "Provide Physiological Inputs" <<physio_input>>
        usecase "Provide Workload/Cognitive Inputs" <<workload_input>>
        usecase "Review & Submit Assessment" <<review_assessment>>
    }
    
    package "ML Prediction & XAI" {
        usecase "Get Stress Prediction" <<predict_stress>>
        usecase "View SHAP Explanations" <<shap_explanation>>
        usecase "View LIME Rules" <<lime_rules>>
    }
    
    package "RAG Coping" {
        usecase "Get Coping Interventions" <<get_coping>>
    }
    
    package "Facial Analysis" {
        usecase "Run Facial Stress Scan" <<facial_scan>>
    }
    
    package "Analytics & Reporting" {
        usecase "View Analytics Dashboard" <<view_analytics>>
        usecase "Export CSV Report" <<export_csv>>
    }
    
    package "Admin Management" {
        usecase "Manage Users" <<manage_users>>
        usecase "View System Analytics" <<system_analytics>>
        usecase "Access Audit Logs" <<audit_logs>>
    }
    
    U --> <<register>>
    U --> <<login>>
    U --> <<submit_assessment>>
    U --> <<physio_input>>
    U --> <<workload_input>>
    U --> <<review_assessment>>
    U --> <<predict_stress>>
    U --> <<shap_explanation>>
    U --> <<lime_rules>>
    U --> <<get_coping>>
    U --> <<facial_scan>>
    U --> <<view_analytics>>
    U <<export_csv>>
    A <<manage_users>>
    A <<system_analytics>>
    A <<audit_logs>>
    
    C --> <<view_analytics>>
    C <<export_csv>>
    
    note "User can perform all assessment and prediction workflows\nClinician can view patient data and analytics\nAdmin has full system management access" as n1
```

### 10.2 Assessment Use Case Flow

```
assessmentFlow
    title Assessment Workflow
    
    participant "User" as User
    participant "Backend API" as Backend
    participant "ML Model" as Model
    participant "Database" as DB
    
    User -> Backend: Submit PSS-10 + physiological + workload data
    Backend -> DB: Store stress_assessment record
    Backend -> Model: Engineer features (25-dim vector)
    Model -> Backend: Predict stress level + confidence
    Backend -> DB: Store prediction record
    Backend -> User: Return prediction + redirect to results
    User -> Backend: Request SHAP/LIME explanations
    Backend -> DB: Store explainability_logs
    Backend -> User: Return SHAP waterfall + LIME rules
    User -> Backend: Request RAG coping interventions
    Backend -> DB: Store rag_coping_logs
    Backend -> User: Return top-3 interventions
```

### 10.3 RAG Coping Use Case Flow

```
ragFlow
    title RAG Coping Intervention Workflow
    
    participant "User" as User
    participant "Backend" as Backend
    participant "Knowledge Base" as KB
    participant "TF-IDF Vectorizer" as Vectorizer
    
    User -> Backend: Provide stress level + SHAP drivers + free-text query
    Backend -> Vectorizer: Transform query to TF-IDF vector
    Vectorizer -> KB: Search cosine similarity
    KB -> Vectorizer: Return similarity scores
    Vectorizer -> Backend: Apply domain boost (+0.25 per matching SHAP driver)
    Backend -> User: Return top-3 interventions with relevance scores
    User -> Backend: Log the RAG query
    Backend -> DB: Store rag_coping_logs entry
```

### 10.4 Facial Stress Scan Use Case Flow

```
facialUseCase
    title Facial Expression Stress Scan Workflow
    
    participant "User" as User
    participant "Browser" as Browser
    participant "ONNX Runtime" as ONNX
    participant "Backend" as Backend
    
    User -> Browser: Allow webcam access
    Browser -> User: Stream webcam frames
    Browser -> ONNX: Send frame every 2.5s (asyncio.to_thread)
    ONNX -> Browser: Emotion probabilities (8 classes) + stress score 0-100
    Browser -> Backend: Send anonymized frame data (base64 JPEG)
    Backend -> ML Model: Stress prediction from facial + questionnaire data
    ML Model -> Backend: Predicted class + confidence
    Backend -> User: Display emotion bars + stress score + tailored RAG interventions
    Note "Frames never stored; privacy-first design" as fn1
```