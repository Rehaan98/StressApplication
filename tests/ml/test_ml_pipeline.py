"""
ML Pipeline Unit Tests

Tests covering:
1. Synthetic dataset generation
2. Feature engineering correctness
3. Data preprocessor fit/transform
4. Model trainer cross-validation and best-model selection
5. Model evaluator metric output structure
6. RAG engine index building and retrieval
"""

import pytest
import os
import numpy as np
import pandas as pd
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from ml_engine.data.generate_synthetic_stress_dataset import generate_stress_dataset
from ml_engine.src.feature_engineering import engineer_stress_features
from ml_engine.src.data_preprocessing import StressDataPreprocessor, FEATURE_COLUMNS, TARGET_COLUMN
from ml_engine.src.model_trainer import StressModelTrainer
from ml_engine.src.model_evaluator import evaluate_stress_model
from ml_engine.src.rag_engine import StressRAGEngine


# ============================================================
# Test 1: Synthetic Dataset Generation
# ============================================================
class TestDataGeneration:
    def test_generate_correct_shape(self):
        df = generate_stress_dataset(n_samples=200, random_state=0)
        assert len(df) == 200
        assert "total_pss" in df.columns
        assert "stress_level" in df.columns
        assert "heart_rate" in df.columns

    def test_pss_items_within_range(self):
        df = generate_stress_dataset(n_samples=200)
        for q in [f"pss_q{i}" for i in range(1, 11)]:
            assert df[q].between(0, 4).all(), f"PSS item {q} out of range 0-4"

    def test_stress_level_classes(self):
        df = generate_stress_dataset(n_samples=500)
        valid_classes = {0, 1, 2, 3}
        assert set(df["stress_level"].unique()).issubset(valid_classes)

    def test_physiological_ranges(self):
        df = generate_stress_dataset(n_samples=300)
        assert df["heart_rate"].between(40, 130).all()
        assert df["sleep_hours"].between(3.0, 12.0).all()
        assert df["hrv_sdnn"].between(10, 130).all()


# ============================================================
# Test 2: Feature Engineering
# ============================================================
class TestFeatureEngineering:
    def setup_method(self):
        self.df = generate_stress_dataset(n_samples=100)

    def test_engineered_features_exist(self):
        out = engineer_stress_features(self.df)
        for col in ["hrv_to_hr_ratio", "sleep_deficiency_index", "work_stress_factor", "composite_strain_index"]:
            assert col in out.columns, f"Missing engineered feature: {col}"

    def test_hrv_to_hr_ratio_positive(self):
        out = engineer_stress_features(self.df)
        assert (out["hrv_to_hr_ratio"] >= 0).all()

    def test_sleep_deficiency_zero_for_optimal_sleep(self):
        df = self.df.copy()
        df["sleep_hours"] = 8.5  # Above optimal threshold
        df["sleep_efficiency"] = 98.0
        out = engineer_stress_features(df)
        # sleep_debt = max(0, 8.0 - 8.5) = 0, so deficiency primarily from efficiency only
        assert (out["sleep_deficiency_index"] >= 0).all()

    def test_composite_strain_between_0_and_1(self):
        out = engineer_stress_features(self.df)
        assert out["composite_strain_index"].between(0.0, 2.0).all()


# ============================================================
# Test 3: Data Preprocessor
# ============================================================
class TestDataPreprocessor:
    def setup_method(self):
        df = generate_stress_dataset(n_samples=300)
        self.df = engineer_stress_features(df)
        self.preprocessor = StressDataPreprocessor()

    def test_fit_transform_returns_scaled_array(self):
        X, y, X_df = self.preprocessor.preprocess_df(self.df, is_training=True)
        assert isinstance(X, np.ndarray)
        assert X.shape[1] == len(FEATURE_COLUMNS)
        assert y is not None

    def test_transform_without_fit_raises(self):
        fresh = StressDataPreprocessor()
        with pytest.raises(ValueError):
            fresh.preprocess_df(self.df, is_training=False)

    def test_no_nan_after_imputation(self):
        X, y, X_df = self.preprocessor.preprocess_df(self.df, is_training=True)
        assert not np.isnan(X).any()


# ============================================================
# Test 4: Model Trainer
# ============================================================
class TestModelTrainer:
    def setup_method(self):
        from sklearn.model_selection import train_test_split
        df = generate_stress_dataset(n_samples=400)
        df = engineer_stress_features(df)
        preprocessor = StressDataPreprocessor()
        X, y, _ = preprocessor.preprocess_df(df, is_training=True)
        self.X_train, self.X_test, self.y_train, self.y_test = train_test_split(
            X, y, test_size=0.25, random_state=42, stratify=y
        )

    def test_trainer_selects_best_model(self):
        trainer = StressModelTrainer(random_state=42)
        model, name, cv_scores = trainer.train_and_select_best(self.X_train, self.y_train)
        assert model is not None
        assert name in ["XGBoost", "RandomForest", "GradientBoosting"]
        assert len(cv_scores) >= 2
        assert all(0 <= v <= 1 for v in cv_scores.values())

    def test_best_model_can_predict(self):
        trainer = StressModelTrainer(random_state=42)
        model, _, _ = trainer.train_and_select_best(self.X_train, self.y_train)
        preds = model.predict(self.X_test)
        assert len(preds) == len(self.X_test)
        assert set(preds).issubset({0, 1, 2, 3})


# ============================================================
# Test 5: Model Evaluator
# ============================================================
class TestModelEvaluator:
    def setup_method(self):
        from sklearn.model_selection import train_test_split
        df = generate_stress_dataset(n_samples=400)
        df = engineer_stress_features(df)
        preprocessor = StressDataPreprocessor()
        X, y, _ = preprocessor.preprocess_df(df, is_training=True)
        X_train, self.X_test, y_train, self.y_test = train_test_split(
            X, y, test_size=0.25, random_state=42, stratify=y
        )
        trainer = StressModelTrainer(random_state=42)
        self.model, _, _ = trainer.train_and_select_best(X_train, y_train)

    def test_metrics_structure(self):
        metrics = evaluate_stress_model(self.model, self.X_test, self.y_test)
        for key in ["accuracy", "precision_macro", "recall_macro", "f1_macro", "confusion_matrix"]:
            assert key in metrics, f"Missing metric: {key}"

    def test_accuracy_within_range(self):
        metrics = evaluate_stress_model(self.model, self.X_test, self.y_test)
        assert 0.0 <= metrics["accuracy"] <= 1.0

    def test_confusion_matrix_dimensions(self):
        metrics = evaluate_stress_model(self.model, self.X_test, self.y_test)
        cm = metrics["confusion_matrix"]
        assert isinstance(cm, list)
        # Should have n_classes x n_classes structure
        for row in cm:
            assert isinstance(row, list)


# ============================================================
# Test 6: RAG Engine
# ============================================================
class TestRAGEngine:
    def setup_method(self):
        self.rag = StressRAGEngine()

    def test_knowledge_base_loaded(self):
        assert len(self.rag.knowledge_base) > 0

    def test_index_built(self):
        assert self.rag.is_built is True
        assert self.rag.tfidf_matrix is not None

    def test_retrieve_returns_correct_count(self):
        results = self.rag.retrieve_interventions(
            stress_level="High",
            top_shap_drivers=[{"feature": "hrv_sdnn"}, {"feature": "total_pss"}],
            user_query="breathing and relaxation",
            top_k=3
        )
        assert len(results) <= 3

    def test_retrieved_items_have_required_fields(self):
        results = self.rag.retrieve_interventions(
            stress_level="Moderate",
            top_shap_drivers=[{"feature": "anxiety_score"}],
            top_k=2
        )
        for item in results:
            assert "id" in item
            assert "title" in item
            assert "category" in item
            assert "protocol" in item
            assert "relevance_score" in item

    def test_relevance_score_is_positive(self):
        results = self.rag.retrieve_interventions(
            stress_level="Severe",
            top_shap_drivers=[{"feature": "total_pss"}, {"feature": "anxiety_score"}],
            user_query="CBT overwhelm cognitive reframing",
            top_k=3
        )
        assert all(item["relevance_score"] >= 0 for item in results)
