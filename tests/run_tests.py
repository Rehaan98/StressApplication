"""
Standard Python Unittest Suite for ML Engine and API Components
"""

import unittest
import os
import sys
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ml_engine.data.generate_synthetic_stress_dataset import generate_stress_dataset
from ml_engine.src.feature_engineering import engineer_stress_features
from ml_engine.src.data_preprocessing import StressDataPreprocessor
from ml_engine.src.model_trainer import StressModelTrainer
from ml_engine.src.model_evaluator import evaluate_stress_model
from ml_engine.src.rag_engine import StressRAGEngine
from backend.app.core.security import get_password_hash, verify_password, create_access_token, decode_access_token

class TestMLPipeline(unittest.TestCase):

    def test_synthetic_data_generation(self):
        df = generate_stress_dataset(n_samples=100, random_state=42)
        self.assertEqual(len(df), 100)
        self.assertIn("total_pss", df.columns)
        self.assertIn("stress_level", df.columns)
        self.assertTrue(df["heart_rate"].between(40, 130).all())

    def test_feature_engineering(self):
        df = generate_stress_dataset(n_samples=50, random_state=42)
        df_eng = engineer_stress_features(df)
        self.assertIn("hrv_to_hr_ratio", df_eng.columns)
        self.assertIn("sleep_deficiency_index", df_eng.columns)
        self.assertIn("work_stress_factor", df_eng.columns)
        self.assertIn("composite_strain_index", df_eng.columns)

    def test_preprocessor(self):
        df = generate_stress_dataset(n_samples=100, random_state=42)
        df_eng = engineer_stress_features(df)
        preprocessor = StressDataPreprocessor()
        X, y, X_df = preprocessor.preprocess_df(df_eng, is_training=True)
        self.assertIsInstance(X, np.ndarray)
        self.assertFalse(np.isnan(X).any())

    def test_model_training_and_evaluation(self):
        df = generate_stress_dataset(n_samples=200, random_state=42)
        df_eng = engineer_stress_features(df)
        preprocessor = StressDataPreprocessor()
        X, y, _ = preprocessor.preprocess_df(df_eng, is_training=True)
        
        trainer = StressModelTrainer(random_state=42)
        best_model, name, cv_scores = trainer.train_and_select_best(X, y)
        self.assertIsNotNone(best_model)
        self.assertIn(name, ["XGBoost", "RandomForest", "GradientBoosting"])

        metrics = evaluate_stress_model(best_model, X, y)
        self.assertGreaterEqual(metrics["accuracy"], 0.80)
        self.assertGreaterEqual(metrics["f1_macro"], 0.75)

    def test_rag_engine(self):
        rag = StressRAGEngine()
        results = rag.retrieve_interventions(
            stress_level="High",
            top_shap_drivers=[{"feature": "hrv_sdnn"}, {"feature": "total_pss"}],
            user_query="breathing and relaxation",
            top_k=3
        )
        self.assertLessEqual(len(results), 3)
        for item in results:
            self.assertIn("title", item)
            self.assertIn("protocol", item)
            self.assertGreaterEqual(item["relevance_score"], 0.0)

class TestSecurity(unittest.TestCase):

    def test_password_hashing(self):
        pwd = "SecretPassWord123!"
        hashed = get_password_hash(pwd)
        self.assertTrue(verify_password(pwd, hashed))
        self.assertFalse(verify_password("WrongPassword", hashed))

    def test_jwt_token(self):
        payload = {"sub": "user@stressai.com", "role": "user"}
        token = create_access_token(payload)
        decoded = decode_access_token(token)
        self.assertIsNotNone(decoded)
        self.assertEqual(decoded["sub"], "user@stressai.com")
        self.assertEqual(decoded["role"], "user")

if __name__ == "__main__":
    unittest.main()
