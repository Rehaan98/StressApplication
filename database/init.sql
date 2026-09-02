-- ============================================================
-- Psychological Stress AI - PostgreSQL Database Schema
-- ============================================================

-- Enable pgvector extension for future vector search support
-- CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================
-- TABLE: users
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    id          VARCHAR(36)  PRIMARY KEY,
    email       VARCHAR(255) UNIQUE NOT NULL,
    full_name   VARCHAR(255) NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    role        VARCHAR(50)  NOT NULL DEFAULT 'user' CHECK (role IN ('admin', 'clinician', 'user')),
    is_active   BOOLEAN      NOT NULL DEFAULT TRUE,
    is_verified BOOLEAN      NOT NULL DEFAULT FALSE,
    avatar_url  VARCHAR(512),
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_role  ON users(role);

-- ============================================================
-- TABLE: stress_assessments
-- ============================================================
CREATE TABLE IF NOT EXISTS stress_assessments (
    id                  VARCHAR(36)   PRIMARY KEY,
    user_id             VARCHAR(36)   NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    -- PSS-10 Items
    pss_q1              SMALLINT      NOT NULL CHECK (pss_q1 BETWEEN 0 AND 4),
    pss_q2              SMALLINT      NOT NULL CHECK (pss_q2 BETWEEN 0 AND 4),
    pss_q3              SMALLINT      NOT NULL CHECK (pss_q3 BETWEEN 0 AND 4),
    pss_q4              SMALLINT      NOT NULL CHECK (pss_q4 BETWEEN 0 AND 4),
    pss_q5              SMALLINT      NOT NULL CHECK (pss_q5 BETWEEN 0 AND 4),
    pss_q6              SMALLINT      NOT NULL CHECK (pss_q6 BETWEEN 0 AND 4),
    pss_q7              SMALLINT      NOT NULL CHECK (pss_q7 BETWEEN 0 AND 4),
    pss_q8              SMALLINT      NOT NULL CHECK (pss_q8 BETWEEN 0 AND 4),
    pss_q9              SMALLINT      NOT NULL CHECK (pss_q9 BETWEEN 0 AND 4),
    pss_q10             SMALLINT      NOT NULL CHECK (pss_q10 BETWEEN 0 AND 4),
    total_pss           SMALLINT      NOT NULL CHECK (total_pss BETWEEN 0 AND 40),
    -- Physiological
    heart_rate          NUMERIC(5,1)  NOT NULL,
    hrv_sdnn            NUMERIC(6,1)  NOT NULL,
    sleep_hours         NUMERIC(4,1)  NOT NULL,
    sleep_efficiency    NUMERIC(5,1)  NOT NULL,
    physical_activity_min NUMERIC(6,1) NOT NULL,
    -- Workload & Cognitive
    work_hours          NUMERIC(4,1)  NOT NULL,
    screen_time_hours   NUMERIC(4,1)  NOT NULL,
    breaks_per_day      SMALLINT      NOT NULL,
    sentiment_score     NUMERIC(4,2)  NOT NULL,
    anxiety_score       NUMERIC(4,1)  NOT NULL,
    notes               TEXT,
    created_at          TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_assessments_user_id   ON stress_assessments(user_id);
CREATE INDEX IF NOT EXISTS idx_assessments_created_at ON stress_assessments(created_at DESC);

-- ============================================================
-- TABLE: predictions
-- ============================================================
CREATE TABLE IF NOT EXISTS predictions (
    id                  VARCHAR(36)   PRIMARY KEY,
    assessment_id       VARCHAR(36)   NOT NULL REFERENCES stress_assessments(id) ON DELETE CASCADE,
    user_id             VARCHAR(36)   NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    predicted_class_id  SMALLINT      NOT NULL CHECK (predicted_class_id BETWEEN 0 AND 3),
    stress_level        VARCHAR(50)   NOT NULL CHECK (stress_level IN ('Low','Moderate','High','Severe')),
    confidence_score    NUMERIC(6,4)  NOT NULL,
    class_probabilities JSONB         NOT NULL,
    created_at          TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_predictions_user_id   ON predictions(user_id);
CREATE INDEX IF NOT EXISTS idx_predictions_created_at ON predictions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_predictions_level     ON predictions(stress_level);

-- ============================================================
-- TABLE: explainability_logs
-- ============================================================
CREATE TABLE IF NOT EXISTS explainability_logs (
    id              VARCHAR(36)  PRIMARY KEY,
    prediction_id   VARCHAR(36)  NOT NULL REFERENCES predictions(id) ON DELETE CASCADE,
    user_id         VARCHAR(36)  NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    shap_top_drivers JSONB       NOT NULL,
    lime_rules      JSONB        NOT NULL,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_xai_logs_prediction_id ON explainability_logs(prediction_id);
CREATE INDEX IF NOT EXISTS idx_xai_logs_user_id       ON explainability_logs(user_id);

-- ============================================================
-- TABLE: rag_coping_logs
-- ============================================================
CREATE TABLE IF NOT EXISTS rag_coping_logs (
    id                      VARCHAR(36)   PRIMARY KEY,
    user_id                 VARCHAR(36)   NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    prediction_id           VARCHAR(36)   REFERENCES predictions(id) ON DELETE SET NULL,
    query_text              TEXT,
    retrieved_interventions JSONB         NOT NULL,
    created_at              TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rag_logs_user_id ON rag_coping_logs(user_id);

-- ============================================================
-- TABLE: audit_logs
-- ============================================================
CREATE TABLE IF NOT EXISTS audit_logs (
    id          VARCHAR(36)  PRIMARY KEY,
    user_id     VARCHAR(36),
    action      VARCHAR(100) NOT NULL,
    ip_address  VARCHAR(45),
    details     JSONB,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id    ON audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action     ON audit_logs(action);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at DESC);

-- ============================================================
-- Seed default accounts
-- bcrypt (12 rounds) hashes:
--   admin@stressai.com    / Admin@StressAI2026
--   dr.sarah@clinic.com   / Clinician@2026
--   user@stressai.com     / User@2026
-- ============================================================
INSERT INTO users (id, email, full_name, hashed_password, role, is_active, is_verified)
VALUES (
    'admin-root-000-0000-000000000001',
    'admin@stressai.com',
    'Platform Administrator',
    '$2b$12$W8dTgTRLrSMvOE0wfpOKPe.wpSvrOyaniKw8CcozEFFstEdWUSKMC',
    'admin',
    TRUE,
    TRUE
) ON CONFLICT (email) DO NOTHING;

INSERT INTO users (id, email, full_name, hashed_password, role, is_active, is_verified)
VALUES (
    'clin-root-000-0000-000000000001',
    'dr.sarah@clinic.com',
    'Dr. Sarah Connor',
    '$2b$12$uH9oqIg72oQULw6gCl5QceUYecv0n7FbPJqfL9iizhU57OxJvmBGC',
    'clinician',
    TRUE,
    TRUE
) ON CONFLICT (email) DO NOTHING;

INSERT INTO users (id, email, full_name, hashed_password, role, is_active, is_verified)
VALUES (
    'user-root-000-0000-000000000001',
    'user@stressai.com',
    'Demo User',
    '$2b$12$mmtqEMnKnzFG5R2PIAvUKOSTQjs74t06YL7qmWAw4o3Sq/FxNzC.y',
    'user',
    TRUE,
    TRUE
) ON CONFLICT (email) DO NOTHING;
