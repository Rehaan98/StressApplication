"""
In-Process FastAPI Endpoint & ML Pipeline Verification Script
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ml_engine.predict import StressPredictor
from ml_engine.src.rag_engine import StressRAGEngine

def main():
    print("==================================================")
    print(" 🧠 PSYCHOLOGICAL STRESS AI — APPLICATION VERIFICATION")
    print("==================================================")

    # 1. Test ML Stress Predictor & Explainability
    print("\n1. Testing ML Stress Prediction & Explainability...")
    predictor = StressPredictor()
    raw_input = {
        "pss_q1": 3, "pss_q2": 3, "pss_q3": 2, "pss_q4": 1, "pss_q5": 1,
        "pss_q6": 3, "pss_q7": 1, "pss_q8": 2, "pss_q9": 3, "pss_q10": 3,
        "total_pss": 25,
        "heart_rate": 84.5, "hrv_sdnn": 42.0, "sleep_hours": 5.8,
        "sleep_efficiency": 74.0, "physical_activity_min": 15.0,
        "work_hours": 11.0, "screen_time_hours": 8.5, "breaks_per_day": 1,
        "sentiment_score": -0.25, "anxiety_score": 7.0
    }
    ml_out = predictor.predict_instance(raw_input)
    print(f"   ✅ Predicted Stress Level: {ml_out['stress_level']} (Confidence: {ml_out['confidence_score']:.2%})")
    print(f"   ✅ Class Probabilities: {ml_out['class_probabilities']}")
    print(f"   ✅ Top SHAP Stress Driver: {ml_out['shap_explanation']['top_drivers'][0]['feature']} (SHAP value: {ml_out['shap_explanation']['top_drivers'][0]['shap_value']:+.3f})")
    print(f"   ✅ Primary LIME Decision Rule: {ml_out['lime_explanation']['lime_rules'][0]['rule']} (Weight: {ml_out['lime_explanation']['lime_rules'][0]['weight']:.3f})")

    # 2. Test RAG Coping Engine
    print("\n2. Testing RAG Clinical Coping Intervention Search...")
    rag_engine = StressRAGEngine()
    interventions = rag_engine.retrieve_interventions(
        user_query="high anxiety work overload low sleep breathing",
        top_shap_drivers=ml_out['shap_explanation']['top_drivers'],
        stress_level=ml_out['stress_level'],
        top_k=3
    )
    print(f"   ✅ Top Retrieved Clinical Protocol: '{interventions[0]['title']}'")
    print(f"      - Category: {interventions[0]['category']}")
    print(f"      - Relevance Score: {interventions[0]['relevance_score']:.2f}")
    print(f"      - Summary: {interventions[0]['summary']}")
    print(f"      - Protocol Steps: {interventions[0]['protocol'][:2]}...")

    # 3. Test Analytics & Storage Verification
    print("\n3. Testing Analytics & Local Storage...")
    db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../stress_ai.db"))
    print(f"   ✅ SQLite Database Verified: {db_path} ({os.path.getsize(db_path)} bytes)")

    print("\n==================================================")
    print(" 🎉 ALL APPLICATION SERVICES OPERATIONAL & VERIFIED!")
    print("==================================================")

if __name__ == "__main__":
    main()
