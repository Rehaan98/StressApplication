"""
Model Trainer Module for Psychological Stress AI

Trains XGBoost, Random Forest, and Gradient Boosting Classifiers for multi-class
stress level prediction (Low, Moderate, High, Severe).
"""

from typing import Dict, Any, Tuple
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.model_selection import GridSearchCV, StratifiedKFold
import joblib

class StressModelTrainer:
    def __init__(self, random_state: int = 42):
        self.random_state = random_state
        self.best_model = None
        self.model_name = ""
        self.cv_results = {}

    def train_and_select_best(self, X_train: np.ndarray, y_train: np.ndarray) -> Tuple[Any, str, Dict[str, float]]:
        cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=self.random_state)
        
        models = {
            "RandomForest": RandomForestClassifier(
                n_estimators=150,
                max_depth=10,
                min_samples_split=4,
                random_state=self.random_state
            ),
            "GradientBoosting": GradientBoostingClassifier(
                n_estimators=120,
                max_depth=4,
                learning_rate=0.1,
                random_state=self.random_state
            )
        }
        
        try:
            from xgboost import XGBClassifier
            models["XGBoost"] = XGBClassifier(
                n_estimators=150,
                max_depth=5,
                learning_rate=0.08,
                subsample=0.85,
                colsample_bytree=0.85,
                random_state=self.random_state,
                eval_metric="mlogloss"
            )
        except Exception:
            pass # Fall back to RandomForest and GradientBoosting if XGBoost OpenMP runtime unavailable
        
        scores = {}
        fitted_models = {}
        
        for name, model in models.items():
            grid = GridSearchCV(
                estimator=model,
                param_grid={}, # Base train evaluation across 5 folds
                cv=cv,
                scoring="f1_macro",
                n_jobs=-1
            )
            grid.fit(X_train, y_train)
            scores[name] = float(grid.best_score_)
            fitted_models[name] = grid.best_estimator_
            
        best_name = max(scores, key=scores.get)
        self.best_model = fitted_models[best_name]
        self.model_name = best_name
        self.cv_results = scores
        
        return self.best_model, self.model_name, self.cv_results

    def save(self, filepath: str):
        joblib.dump({"model": self.best_model, "model_name": self.model_name, "cv_results": self.cv_results}, filepath)

    def load(self, filepath: str):
        data = joblib.load(filepath)
        self.best_model = data["model"]
        self.model_name = data["model_name"]
        self.cv_results = data["cv_results"]
