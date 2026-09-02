"""
Train Script for Psychological Stress AI ML & RAG Pipeline

Orchestrates:
1. Synthetic data generation (if dataset missing)
2. Feature engineering & data preprocessing
3. Model training & 5-fold cross-validation
4. Performance evaluation (Accuracy, F1, Precision, Recall, Confusion Matrix)
5. XAI Explainer & RAG Engine initialization
6. Artifact saving to ml_engine/models/
"""

import os
import json
import numpy as np
import pandas as pd
from ml_engine.data.generate_synthetic_stress_dataset import generate_stress_dataset
from ml_engine.src.feature_engineering import engineer_stress_features
from ml_engine.src.data_preprocessing import StressDataPreprocessor, FEATURE_COLUMNS, TARGET_COLUMN
from ml_engine.src.model_trainer import StressModelTrainer
from ml_engine.src.model_evaluator import evaluate_stress_model
from ml_engine.src.explainable_ai import StressExplainer
from ml_engine.src.rag_engine import StressRAGEngine

def run_training_pipeline():
    base_dir = os.path.dirname(__file__)
    data_dir = os.path.join(base_dir, "data")
    models_dir = os.path.join(base_dir, "models")
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(models_dir, exist_ok=True)
    
    csv_path = os.path.join(data_dir, "synthetic_stress_data.csv")
    if not os.path.exists(csv_path):
        print("Generating synthetic stress dataset...")
        df = generate_stress_dataset(n_samples=3000)
        df.to_csv(csv_path, index=False)
    else:
        df = pd.read_csv(csv_path)
        
    print(f"Dataset loaded with {len(df)} samples.")
    
    # 1. Feature Engineering
    df = engineer_stress_features(df)
    
    # 2. Data Preprocessing
    preprocessor = StressDataPreprocessor()
    X_scaled, y, X_df = preprocessor.preprocess_df(df, is_training=True)
    
    from sklearn.model_selection import train_test_split
    X_train, X_test, y_train, y_test = train_test_split(X_scaled, y, test_size=0.2, random_state=42, stratify=y)
    
    # 3. Model Training
    print("Training ML Models (XGBoost, Random Forest, Gradient Boosting)...")
    trainer = StressModelTrainer(random_state=42)
    best_model, model_name, cv_scores = trainer.train_and_select_best(X_train, y_train)
    print(f"Best Model Selected: {model_name} with CV F1-Score: {cv_scores[model_name]:.4f}")
    
    # 4. Evaluation
    eval_metrics = evaluate_stress_model(best_model, X_test, y_test)
    print("Evaluation Results on Test Set:")
    print(json.dumps(eval_metrics, indent=2))
    
    # 5. Save Artifacts
    preprocessor_path = os.path.join(models_dir, "preprocessor.joblib")
    model_path = os.path.join(models_dir, "stress_model.joblib")
    metrics_path = os.path.join(models_dir, "eval_metrics.json")
    
    preprocessor.save(preprocessor_path)
    trainer.save(model_path)
    
    with open(metrics_path, "w") as f:
        json.dump(eval_metrics, f, indent=2)
        
    # 6. Initialize RAG Index
    rag_engine = StressRAGEngine()
    rag_engine.save(os.path.join(models_dir, "rag_engine.joblib"))
    
    print(f"Artifacts successfully saved to {models_dir}")

if __name__ == "__main__":
    run_training_pipeline()
