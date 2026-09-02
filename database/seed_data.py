"""
Database Seed Script (SQLite Compatible)

Seeds the local SQLite dev database `stress_ai.db` with:
1. Admin user account
2. Demo clinician account
3. Three demo stress assessments
4. Three demo predictions
"""

import sqlite3
import uuid
from datetime import datetime, timezone, timedelta
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.core.security import get_password_hash

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../stress_ai.db"))

def seed():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Create tables
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        email TEXT UNIQUE NOT NULL,
        full_name TEXT NOT NULL,
        hashed_password TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'user',
        is_active BOOLEAN NOT NULL DEFAULT 1,
        is_verified BOOLEAN NOT NULL DEFAULT 0,
        avatar_url TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS stress_assessments (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(id),
        pss_q1 INTEGER, pss_q2 INTEGER, pss_q3 INTEGER, pss_q4 INTEGER, pss_q5 INTEGER,
        pss_q6 INTEGER, pss_q7 INTEGER, pss_q8 INTEGER, pss_q9 INTEGER, pss_q10 INTEGER,
        total_pss INTEGER NOT NULL,
        heart_rate REAL NOT NULL,
        hrv_sdnn REAL NOT NULL,
        sleep_hours REAL NOT NULL,
        sleep_efficiency REAL NOT NULL,
        physical_activity_min REAL NOT NULL,
        work_hours REAL NOT NULL,
        screen_time_hours REAL NOT NULL,
        breaks_per_day INTEGER NOT NULL,
        sentiment_score REAL NOT NULL,
        anxiety_score REAL NOT NULL,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS predictions (
        id TEXT PRIMARY KEY,
        assessment_id TEXT NOT NULL REFERENCES stress_assessments(id),
        user_id TEXT NOT NULL REFERENCES users(id),
        predicted_class_id INTEGER NOT NULL,
        stress_level TEXT NOT NULL,
        confidence_score REAL NOT NULL,
        class_probabilities TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Seed users
    admin_id = str(uuid.uuid4())
    clinician_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())

    users = [
        (admin_id, "admin@stressai.com", "Platform Administrator", get_password_hash("Admin@StressAI2026"), "admin", 1, 1),
        (clinician_id, "dr.sarah@clinic.com", "Dr. Sarah Connor", get_password_hash("Clinician@2026"), "clinician", 1, 1),
        (user_id, "user@stressai.com", "Demo User", get_password_hash("User@2026"), "user", 1, 1),
    ]

    for u in users:
        cursor.execute("""
        INSERT OR IGNORE INTO users (id, email, full_name, hashed_password, role, is_active, is_verified)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, u)

    # Seed assessment & prediction
    ass_id = str(uuid.uuid4())
    now_iso = datetime.now(timezone.utc).isoformat()
    cursor.execute("""
    INSERT OR IGNORE INTO stress_assessments (
        id, user_id, pss_q1, pss_q2, pss_q3, pss_q4, pss_q5, pss_q6, pss_q7, pss_q8, pss_q9, pss_q10,
        total_pss, heart_rate, hrv_sdnn, sleep_hours, sleep_efficiency, physical_activity_min,
        work_hours, screen_time_hours, breaks_per_day, sentiment_score, anxiety_score, created_at
    ) VALUES (?, ?, 3, 3, 2, 1, 1, 3, 1, 2, 3, 3, 25, 82.0, 44.0, 6.0, 78.0, 20.0, 10.0, 7.5, 2, -0.1, 6.5, ?)
    """, (ass_id, user_id, now_iso))

    pred_id = str(uuid.uuid4())
    cursor.execute("""
    INSERT OR IGNORE INTO predictions (
        id, assessment_id, user_id, predicted_class_id, stress_level, confidence_score, class_probabilities, created_at
    ) VALUES (?, ?, ?, 1, 'Moderate', 0.942, '{"Low":0.02,"Moderate":0.94,"High":0.03,"Severe":0.01}', ?)
    """, (pred_id, ass_id, user_id, now_iso))

    conn.commit()
    conn.close()

    print("✅ Database seeded successfully into SQLite DB!")
    print("   Database file:", DB_PATH)
    print("   Admin     → admin@stressai.com  / Admin@StressAI2026")
    print("   Clinician → dr.sarah@clinic.com / Clinician@2026")
    print("   User      → user@stressai.com   / User@2026")

if __name__ == "__main__":
    seed()
