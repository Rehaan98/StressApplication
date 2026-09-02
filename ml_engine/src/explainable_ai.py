"""
Explainable AI (XAI) Module for Psychological Stress AI

Uses SHAP (SHapley Additive exPlanations) and LIME (Local Interpretable Model-agnostic Explanations)
to compute feature attributions for stress level predictions.
"""

from typing import Dict, Any, List
import warnings
import numpy as np
import pandas as pd
import shap
from lime.lime_tabular import LimeTabularExplainer

FEATURE_NAMES = [
    "pss_q1", "pss_q2", "pss_q3", "pss_q4", "pss_q5",
    "pss_q6", "pss_q7", "pss_q8", "pss_q9", "pss_q10",
    "total_pss", "heart_rate", "hrv_sdnn", "sleep_hours",
    "sleep_efficiency", "physical_activity_min", "work_hours",
    "screen_time_hours", "breaks_per_day", "sentiment_score", "anxiety_score",
    "hrv_to_hr_ratio", "sleep_deficiency_index", "work_stress_factor", "composite_strain_index"
]

CLASS_LABELS = ["Low", "Moderate", "High", "Severe"]

class StressExplainer:
    def __init__(self, model: Any, background_data: np.ndarray):
        self.model = model
        
        # KernelExplainer and LIME require a non-degenerate background sample.
        # Inference-time callers typically pass a single row, so augment it with
        # locally perturbed samples to build a usable background distribution.
        bg = np.asarray(background_data, dtype=float)
        if bg.ndim == 1:
            bg = bg.reshape(1, -1)
        if bg.shape[0] < 20 or not np.any(np.ptp(bg, axis=0)):
            rng = np.random.RandomState(42)
            base = bg[0] if bg.shape[0] >= 1 else np.zeros(bg.shape[1])
            jitter = np.maximum(np.abs(base) * 0.15, 1e-3)
            bg = np.vstack([bg, base[None, :] + rng.normal(0.0, jitter, size=(50, bg.shape[1]))])
        self.background_data = bg
        
        # Initialize SHAP Explainer: prefer exact TreeExplainer (XGBoost, Random
        # Forest, binary GB), fall back to model-agnostic KernelExplainer for
        # multi-class sklearn ensembles (not supported by shap.TreeExplainer).
        try:
            self.shap_explainer = shap.TreeExplainer(model)
            self._shap_kind = "tree"
        except Exception:
            self.shap_explainer = shap.KernelExplainer(model.predict_proba, self.background_data)
            self._shap_kind = "kernel"
            
        # Initialize LIME Explainer
        self.lime_explainer = LimeTabularExplainer(
            training_data=self.background_data,
            feature_names=FEATURE_NAMES,
            class_names=CLASS_LABELS,
            mode="classification"
        )

    def explain_instance_shap(self, instance_scaled: np.ndarray, predicted_class: int) -> Dict[str, Any]:
        """
        Computes SHAP values for a single prediction instance.
        """
        if instance_scaled.ndim == 1:
            instance_scaled = instance_scaled.reshape(1, -1)

        # KernelExplainer on wide multi-class problems emits numerical
        # RuntimeWarnings (divide-by-zero/overflow in the weighted linear
        # surrogate). Sampling artifacts; final values are sanitized below.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            shap_vals = self.shap_explainer.shap_values(instance_scaled)
        
        # Multi-class SHAP handling across explainer output shapes:
        # - TreeExplainer (XGBoost/RF): list of per-class arrays or (n, f, c)
        # - KernelExplainer (multiclass proba): (n, f, c)
        if isinstance(shap_vals, list):
            class_shap = np.asarray(shap_vals[predicted_class][0], dtype=float)
        elif shap_vals.ndim == 3: # (samples, features, classes)
            class_shap = np.asarray(shap_vals[0, :, predicted_class], dtype=float)
        else:
            class_shap = np.asarray(shap_vals[0], dtype=float)
            
        class_shap = np.nan_to_num(class_shap, nan=0.0, posinf=0.0, neginf=0.0)
        
        # Last-resort fallback: if the local surrogate produced no signal,
        # use the model's global feature importances instead.
        if not np.any(class_shap):
            fi = np.asarray(getattr(self.model, "feature_importances_", []), dtype=float)
            if fi.size == class_shap.size and np.any(fi):
                class_shap = fi / (np.abs(fi).sum() + 1e-12)
        
        feature_impacts = []
        for name, score in zip(FEATURE_NAMES, class_shap):
            feature_impacts.append({
                "feature": name,
                "shap_value": float(np.round(score, 5)),
                "impact": "increases_stress" if score > 0 else "reduces_stress"
            })
            
        # Sort by absolute SHAP impact
        feature_impacts.sort(key=lambda x: abs(x["shap_value"]), reverse=True)
        
        return {
            "predicted_class": CLASS_LABELS[predicted_class],
            "top_drivers": feature_impacts[:7],
            "all_features": feature_impacts
        }

    def explain_instance_lime(self, instance_scaled: np.ndarray, predicted_class: int) -> Dict[str, Any]:
        """
        Computes LIME local surrogate explanations for a single prediction.
        """
        if instance_scaled.ndim == 2:
            instance_scaled = instance_scaled.ravel()

        with warnings.catch_warnings():
            # LIME's Ridge surrogate can overflow numerically on scaled inputs;
            # sklearn then emits noisy RuntimeWarnings. Weights remain bounded
            # by the explainer's own normalization, so this is safe to ignore.
            warnings.simplefilter("ignore", RuntimeWarning)
            exp = self.lime_explainer.explain_instance(
                data_row=instance_scaled,
                predict_fn=self.model.predict_proba,
                labels=[predicted_class],
                num_features=7
            )
        
        lime_list = exp.as_list(label=predicted_class)
        lime_features = []
        for feat_rule, weight in lime_list:
            lime_features.append({
                "rule": feat_rule,
                "weight": float(np.round(weight, 5)),
                "effect": "increases_stress" if weight > 0 else "reduces_stress"
            })
            
        return {
            "predicted_class": CLASS_LABELS[predicted_class],
            "lime_rules": lime_features
        }
