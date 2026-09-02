"""
Inference & Prediction Entrypoint for Psychological Stress AI

Provides single-instance real-time inference, SHAP/LIME explainability,
and RAG intervention retrieval.

Falls back to a rule-based heuristic prediction when trained model artifacts
are not yet present (e.g. before running train.py / train_pipeline.py).
"""

import os
import json
from typing import Dict, Any, List
import numpy as np
import pandas as pd

from ml_engine.src.feature_engineering import engineer_stress_features
from ml_engine.src.data_preprocessing import StressDataPreprocessor, FEATURE_COLUMNS
from ml_engine.src.model_trainer import StressModelTrainer
from ml_engine.src.explainable_ai import StressExplainer, CLASS_LABELS
from ml_engine.src.rag_engine import StressRAGEngine

MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")


def _heuristic_prediction(raw_input: Dict[str, Any]) -> Dict[str, Any]:
    """
    Rule-based fallback when no trained model is available.
    Uses total_pss + composite indicators to estimate stress level.
    """
    total_pss = raw_input.get("total_pss", 20)
    hrv = raw_input.get("hrv_sdnn", 55)
    sleep = raw_input.get("sleep_hours", 7)
    anxiety = raw_input.get("anxiety_score", 5)

    score = (
        (total_pss / 40.0) * 0.40
        + (1 - min(hrv, 100) / 100.0) * 0.25
        + (1 - min(sleep, 8) / 8.0) * 0.20
        + (anxiety / 10.0) * 0.15
    )

    if score < 0.30:
        pred_class, label = 0, "Low"
        probs = [0.80, 0.15, 0.04, 0.01]
    elif score < 0.55:
        pred_class, label = 1, "Moderate"
        probs = [0.05, 0.82, 0.10, 0.03]
    elif score < 0.75:
        pred_class, label = 2, "High"
        probs = [0.02, 0.10, 0.78, 0.10]
    else:
        pred_class, label = 3, "Severe"
        probs = [0.01, 0.04, 0.15, 0.80]

    shap_drivers = [
        {"feature": "total_pss", "shap_value": round((total_pss / 40.0) * 0.40, 4), "impact": "increases_stress"},
        {"feature": "hrv_sdnn", "shap_value": round(-(min(hrv, 100) / 100.0) * 0.25, 4), "impact": "reduces_stress"},
        {"feature": "anxiety_score", "shap_value": round((anxiety / 10.0) * 0.15, 4), "impact": "increases_stress"},
        {"feature": "sleep_hours", "shap_value": round(-(min(sleep, 8) / 8.0) * 0.20, 4), "impact": "reduces_stress"},
    ]

    lime_rules = [
        {"rule": f"total_pss {'>' if total_pss > 14 else '<='} 14.0", "weight": 0.289, "effect": "increases_stress"},
        {"rule": f"hrv_sdnn {'<=' if hrv < 60 else '>'} 60.0", "weight": 0.198, "effect": "increases_stress" if hrv < 60 else "reduces_stress"},
        {"rule": f"anxiety_score {'>' if anxiety > 5 else '<='} 5.0", "weight": 0.172, "effect": "increases_stress"},
    ]

    return {
        "predicted_class_id": pred_class,
        "stress_level": label,
        "confidence_score": round(probs[pred_class], 4),
        "class_probabilities": {CLASS_LABELS[i]: round(p, 4) for i, p in enumerate(probs)},
        "shap_explanation": {"predicted_class": label, "top_drivers": shap_drivers, "all_features": shap_drivers},
        "lime_explanation": {"predicted_class": label, "lime_rules": lime_rules},
        "rag_interventions": [],  # will be filled by RAG engine below
        "_heuristic": True,
    }


class StressPredictor:
    def __init__(self, models_dir: str = MODELS_DIR):
        self.models_dir = models_dir
        self.preprocessor = StressDataPreprocessor()
        self.trainer = StressModelTrainer()
        self.rag_engine = StressRAGEngine()
        self.explainer = None
        self.is_loaded = False

        self.load_artifacts()

    def load_artifacts(self) -> bool:
        preprocessor_path = os.path.join(self.models_dir, "preprocessor.joblib")
        model_path = os.path.join(self.models_dir, "stress_model.joblib")
        rag_path = os.path.join(self.models_dir, "rag_engine.joblib")

        if os.path.exists(preprocessor_path) and os.path.exists(model_path):
            try:
                self.preprocessor.load(preprocessor_path)
                self.trainer.load(model_path)
                if os.path.exists(rag_path):
                    self.rag_engine.load(rag_path)
                self.is_loaded = True
            except Exception as e:
                print(f"[StressPredictor] Warning: could not load model artifacts: {e}")
                self.is_loaded = False
        else:
            print(
                "[StressPredictor] No trained model found. "
                "Run `python -m ml_engine.src.train_pipeline` to train. "
                "Using heuristic fallback for now."
            )
            self.is_loaded = False
        return self.is_loaded

    def predict_instance(self, raw_input: Dict[str, Any]) -> Dict[str, Any]:
        """
        End-to-end inference: feature engineering → preprocessing → model prediction
        → SHAP/LIME explainability → RAG intervention retrieval.

        Falls back to heuristic prediction if model not trained yet.
        """
        if not self.is_loaded:
            self.load_artifacts()

        if not self.is_loaded:
            # Heuristic fallback path
            result = _heuristic_prediction(raw_input)
            # Still retrieve RAG interventions
            try:
                rag_interventions = self.rag_engine.retrieve_interventions(
                    stress_level=result["stress_level"],
                    top_shap_drivers=result["shap_explanation"]["top_drivers"],
                    top_k=3,
                )
                result["rag_interventions"] = rag_interventions
            except Exception:
                pass
            return result

        df_input = pd.DataFrame([raw_input])
        df_engineered = engineer_stress_features(df_input)

        X_scaled, _, X_df = self.preprocessor.preprocess_df(df_engineered, is_training=False)

        model = self.trainer.best_model
        pred_class = int(model.predict(X_scaled)[0])
        probas = (
            model.predict_proba(X_scaled)[0]
            if hasattr(model, "predict_proba")
            else np.array([0.25, 0.25, 0.25, 0.25])
        )
        probas = np.asarray(probas, dtype=float)
        if probas.ndim == 1 and probas.shape[0] < len(CLASS_LABELS):
            padded = np.zeros(len(CLASS_LABELS))
            padded[:probas.shape[0]] = probas
            padded[probas.shape[0]:] = (1.0 - probas.sum()) / max(len(CLASS_LABELS) - probas.shape[0], 1)
            probas = padded
        probas = probas / (probas.sum() + 1e-12)

        confidence = float(np.round(probas[pred_class], 4))
        risk_label = CLASS_LABELS[pred_class]

        # XAI Explanation
        explainer = StressExplainer(model, X_scaled)
        shap_res = explainer.explain_instance_shap(X_scaled[0], pred_class)
        lime_res = explainer.explain_instance_lime(X_scaled[0], pred_class)

        # RAG Interventions
        rag_interventions = self.rag_engine.retrieve_interventions(
            stress_level=risk_label,
            top_shap_drivers=shap_res["top_drivers"],
            top_k=3,
        )

        return {
            "predicted_class_id": pred_class,
            "stress_level": risk_label,
            "confidence_score": confidence,
            "class_probabilities": {
                CLASS_LABELS[i]: float(np.round(p, 4)) for i, p in enumerate(probas)
            },
            "shap_explanation": shap_res,
            "lime_explanation": lime_res,
            "rag_interventions": rag_interventions,
        }


if __name__ == "__main__":
    predictor = StressPredictor()
    sample_input = {
        "pss_q1": 3, "pss_q2": 4, "pss_q3": 3, "pss_q4": 1, "pss_q5": 1,
        "pss_q6": 3, "pss_q7": 1, "pss_q8": 2, "pss_q9": 4, "pss_q10": 3,
        "total_pss": 28, "heart_rate": 88.5, "hrv_sdnn": 32.0, "sleep_hours": 5.0,
        "sleep_efficiency": 70.0, "physical_activity_min": 15, "work_hours": 11.0,
        "screen_time_hours": 9.5, "breaks_per_day": 1, "sentiment_score": -0.45,
        "anxiety_score": 8.0,
    }
    res = predictor.predict_instance(sample_input)
    print(json.dumps(
        {k: v for k, v in res.items() if k != "rag_interventions"},
        indent=2,
        default=str,
    ))
