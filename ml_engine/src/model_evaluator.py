"""
Model Evaluator Module for Psychological Stress AI

Computes multi-class evaluation metrics:
- Accuracy
- Precision (Macro & Weighted)
- Recall (Macro & Weighted)
- F1-Score (Macro & Weighted)
- Confusion Matrix
- ROC-AUC Score (One-vs-Rest)
"""

from typing import Dict, Any
import numpy as np
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    confusion_matrix, roc_auc_score
)

CLASS_NAMES = ["Low", "Moderate", "High", "Severe"]

def evaluate_stress_model(model: Any, X_test: np.ndarray, y_test: np.ndarray) -> Dict[str, Any]:
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test) if hasattr(model, "predict_proba") else None
    
    acc = float(accuracy_score(y_test, y_pred))
    prec_macro = float(precision_score(y_test, y_pred, average="macro", zero_division=0))
    rec_macro = float(recall_score(y_test, y_pred, average="macro", zero_division=0))
    f1_macro = float(f1_score(y_test, y_pred, average="macro", zero_division=0))
    
    cm = confusion_matrix(y_test, y_pred).tolist()
    
    roc_auc = None
    if y_proba is not None:
        try:
            roc_auc = float(roc_auc_score(y_test, y_proba, multi_class="ovr", average="macro"))
        except Exception:
            roc_auc = None
            
    # Per-class metrics
    class_metrics = {}
    for i, name in enumerate(CLASS_NAMES):
        mask = (y_test == i)
        if np.sum(mask) > 0:
            c_acc = float(np.mean(y_pred[mask] == i))
            class_metrics[name] = {
                "support": int(np.sum(mask)),
                "accuracy": np.round(c_acc, 4)
            }
            
    return {
        "accuracy": np.round(acc, 4),
        "precision_macro": np.round(prec_macro, 4),
        "recall_macro": np.round(rec_macro, 4),
        "f1_macro": np.round(f1_macro, 4),
        "roc_auc": np.round(roc_auc, 4) if roc_auc is not None else None,
        "confusion_matrix": cm,
        "class_metrics": class_metrics
    }
