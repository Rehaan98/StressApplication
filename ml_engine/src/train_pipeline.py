"""
ML Training & Pipeline Execution Script

Trains and saves all artifacts to ml_engine/models/ so the predictor can load them.
"""

import os
import sys
import json
import joblib

# Ensure project root is on path when run directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from ml_engine.data.generate_synthetic_stress_dataset import generate_stress_dataset
from ml_engine.src.feature_engineering import engineer_stress_features
from ml_engine.src.data_preprocessing import StressDataPreprocessor
from ml_engine.src.model_trainer import StressModelTrainer
from ml_engine.src.model_evaluator import evaluate_stress_model
from ml_engine.src.rag_engine import StressRAGEngine
from sklearn.model_selection import train_test_split

# Always save to ml_engine/models/ (where predict.py loads from)
MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "models")
os.makedirs(MODEL_DIR, exist_ok=True)


def run_training_pipeline():
    print("1. Generating synthetic multi-modal stress dataset...")
    df = generate_stress_dataset(n_samples=3000, random_state=42)

    print("2. Engineering physiological & psychometric features...")
    df = engineer_stress_features(df)

    print("3. Preprocessing data & scaling features...")
    preprocessor = StressDataPreprocessor()
    X, y, X_df = preprocessor.preprocess_df(df, is_training=True)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    print("4. Training & selecting best ML classifier...")
    trainer = StressModelTrainer(random_state=42)
    best_model, best_name, cv_scores = trainer.train_and_select_best(X_train, y_train)

    print(f"   Best model: {best_name}")
    for name, score in cv_scores.items():
        print(f"   - {name} CV Macro F1: {score:.4f}")

    print("5. Evaluating on test set...")
    metrics = evaluate_stress_model(best_model, X_test, y_test)
    print(f"   Accuracy: {metrics['accuracy']:.4f}  |  Macro F1: {metrics['f1_macro']:.4f}")

    print("6. Saving preprocessor, model, and evaluation metrics...")
    preprocessor.save(os.path.join(MODEL_DIR, "preprocessor.joblib"))
    trainer.save(os.path.join(MODEL_DIR, "stress_model.joblib"))
    with open(os.path.join(MODEL_DIR, "eval_metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)

    print("7. Building & saving RAG TF-IDF knowledge base index...")
    rag = StressRAGEngine()
    rag.save(os.path.join(MODEL_DIR, "rag_engine.joblib"))

    print(f"\nAll artifacts saved to: {os.path.abspath(MODEL_DIR)}")
    print("Training pipeline completed successfully.")
    return metrics


if __name__ == "__main__":
    run_training_pipeline()
