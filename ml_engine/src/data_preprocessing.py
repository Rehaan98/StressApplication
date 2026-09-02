"""
Data Preprocessing Module for Psychological Stress AI

Handles missing value imputation, robust feature scaling, categorical encoding,
and train/test splitting.
"""

from typing import Tuple, Dict, Any
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, RobustScaler
from sklearn.impute import SimpleImputer
import joblib

FEATURE_COLUMNS = [
    "pss_q1", "pss_q2", "pss_q3", "pss_q4", "pss_q5",
    "pss_q6", "pss_q7", "pss_q8", "pss_q9", "pss_q10",
    "total_pss", "heart_rate", "hrv_sdnn", "sleep_hours",
    "sleep_efficiency", "physical_activity_min", "work_hours",
    "screen_time_hours", "breaks_per_day", "sentiment_score", "anxiety_score",
    # Engineered features
    "hrv_to_hr_ratio", "sleep_deficiency_index", "work_stress_factor", "composite_strain_index"
]

TARGET_COLUMN = "stress_level"

class StressDataPreprocessor:
    def __init__(self):
        self.imputer = SimpleImputer(strategy="median")
        self.scaler = RobustScaler()
        self.is_fitted = False

    def preprocess_df(self, df: pd.DataFrame, is_training: bool = True) -> Tuple[np.ndarray, np.ndarray, pd.DataFrame]:
        df = df.copy()
        
        # Ensure engineered features are present
        if "hrv_to_hr_ratio" not in df.columns:
            from ml_engine.src.feature_engineering import engineer_stress_features
            df = engineer_stress_features(df)
            
        X_raw = df[FEATURE_COLUMNS]
        y_raw = df[TARGET_COLUMN].values if TARGET_COLUMN in df.columns else None

        if is_training:
            X_imputed = self.imputer.fit_transform(X_raw)
            X_scaled = self.scaler.fit_transform(X_imputed)
            self.is_fitted = True
        else:
            if not self.is_fitted:
                raise ValueError("Preprocessor must be fitted on training data first!")
            X_imputed = self.imputer.transform(X_raw)
            X_scaled = self.scaler.transform(X_imputed)

        return X_scaled, y_raw, pd.DataFrame(X_imputed, columns=FEATURE_COLUMNS)

    def save(self, filepath: str):
        joblib.dump({"imputer": self.imputer, "scaler": self.scaler, "is_fitted": self.is_fitted}, filepath)

    def load(self, filepath: str):
        data = joblib.load(filepath)
        self.imputer = data["imputer"]
        self.scaler = data["scaler"]
        self.is_fitted = data["is_fitted"]
