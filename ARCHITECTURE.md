# Psychological Stress AI — System Architecture & Technical Specifications

## 1. High-Level Architecture

The **Psychological Stress AI** platform is built as a multi-tier, microservice-ready full-stack application designed for multi-modal psychological stress assessment, explainable machine learning predictions, and Retrieval-Augmented Generation (RAG) clinical coping recommendation.

```
┌──────────────────────────────────────────────────────────────────────────┐
│                   Next.js 14 Web Application (Client)                    │
│   Dashboard · Assessment Form · XAI Viewer · RAG Coping · Admin Panel   │
└────────────────────────────────────┬─────────────────────────────────────┘
                                     │ REST / JSON (JWT Auth)
                                     ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                      FastAPI Asynchronous Backend                        │
│  ┌───────────────────────┬───────────────────────┬────────────────────┐  │
│  │  Auth & RBAC Service  │ Stress Assessment Svc │  Analytics Engine  │  │
│  └───────────────────────┴───────────────────────┴────────────────────┘  │
│  ┌───────────────────────┬───────────────────────┬────────────────────┐  │
│  │   ML Predictor & XAI  │ RAG Coping Generator  │ CSV Report Engine  │  │
│  └───────────────────────┴───────────────────────┴────────────────────┘  │
└───────────────────┬───────────────────┬───────────────────┬──────────────┘
                    │                   │                   │
                    ▼                   ▼                   ▼
     ┌──────────────────────┐ ┌──────────────────┐ ┌──────────────────┐
     │ ML Model & XAI Engine│ │ TF-IDF RAG Index │ │ SQLite / Postgres│
     │ XGBoost / SHAP / LIME│ │  Vector Search   │ │ Relational Store │
     └──────────────────────┘ └──────────────────┘ └──────────────────┘
```

---

## 2. Multi-Modal Feature Pipeline

The machine learning engine combines subjective psychometric tools, physiological telemetry, lifestyle/workload metrics, and cognitive sentiment into a 22-dimensional feature space.

### Input Features & Domain Mapping
1. **Psychometric Score**: PSS-10 total score (range: 0–40), reverse-scored server-side for items 4, 5, 7, and 8.
2. **Physiological Telemetry**:
   - `heart_rate` (BPM)
   - `hrv_sdnn` (ms): Standard deviation of NN intervals — key marker of parasympathetic autonomic tone.
3. **Lifestyle & Sleep Metrics**:
   - `sleep_hours` (hours/night)
   - `sleep_efficiency` (%)
   - `physical_activity_min` (minutes/day)
4. **Workload & Cognitive Metrics**:
   - `work_hours` (hours/day)
   - `screen_time_hours` (hours/day)
   - `breaks_per_day` (count)
   - `sentiment_score` (-1.0 to +1.0): VADER text sentiment from user daily notes.
   - `anxiety_score` (0–10 scale).

### Derived Domain Features (Engineered)
- **HRV-to-HR Ratio**: $\frac{\text{hrv\_sdnn}}{\text{heart\_rate}}$ (Reflects sympathovagal balance).
- **Sleep Deficiency Index**: $\max(0, 8.0 - \text{sleep\_hours}) \times \left(1.0 - \frac{\text{sleep\_efficiency}}{100}\right)$
- **Work Stress Factor**: $\frac{\text{work\_hours} \times \text{screen\_time\_hours}}{\text{breaks\_per\_day} + 1}$
- **Composite Strain Index**: Weighted blend of PSS score, HRV deficiency, sleep deficit, and work stress factor.

---

## 3. Machine Learning & Explainable AI (XAI)

### Model Pipeline
- **Classifier Models**: Evaluates XGBoost, RandomForest, and GradientBoosting classifiers via Stratified $K$-Fold Cross-Validation.
- **Stress Multi-Classes**:
  - `0`: Low Stress
  - `1`: Moderate Stress
  - `2`: High Stress
  - `3`: Severe Stress
- **Target Metrics**: Macro F1-Score $\ge 85\%$, Precision $\ge 90\%$, ROC-AUC $\ge 95\%$.

### XAI Architecture
1. **SHAP (SHapley Additive exPlanations)**:
   - Computes exact marginal contribution of each feature to the log-odds prediction.
   - Identifies positive stress drivers (amplifiers) vs negative stress drivers (protective buffers).
2. **LIME (Local Interpretable Model-agnostic Explanations)**:
   - Constructs a local linear surrogate model around the specific instance.
   - Generates human-interpretable if-then decision rules (e.g., `total_pss > 22.0 AND hrv_sdnn <= 48.5`).

---

## 4. Retrieval-Augmented Generation (RAG) Coping Engine

The RAG engine connects diagnostic model outputs with evidence-based clinical intervention protocols.

### Retrieval Mechanism
1. **Knowledge Base**: Curated index of evidence-based CBT protocols, HRV/vagus nerve breathing exercises, circadian sleep synchronization protocols, and workload boundary strategies.
2. **Hybrid Query Vector**: Combines user free-text query + top SHAP stress drivers + predicted stress level.
3. **TF-IDF + Cosine Similarity**: Computes vector similarity against document embeddings.
4. **Context-Boosted Ranking**: Applies domain multiplier for interventions directly matching top SHAP driver features.

---

## 5. Security & Compliance Architecture

- **Authentication**: OAuth2 Password Flow with JWT Bearer tokens signed via HMAC-SHA256 (`HS256`).
- **Password Security**: Password hashing with `bcrypt` (12 work factor rounds).
- **Role-Based Access Control (RBAC)**:
  - `user`: Submit self-assessments, view personal predictions and coping strategies.
  - `clinician`: View patient assessments, trend analytics, and detailed SHAP/LIME breakdown.
  - `admin`: User administration, model monitoring, audit log oversight.
- **Audit Logging**: All auth events, predictions, and RAG queries are stored in an append-only audit trail.
