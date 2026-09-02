"""
Analytics & Aggregation Business Logic Service
"""

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from backend.app.models.assessment import StressAssessment
from backend.app.models.prediction import Prediction
from backend.app.models.facial_analysis import FacialAnalysis
from backend.app.models.user import User

EVAL_METRICS_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "ml_engine", "models", "eval_metrics.json")
)


def _load_model_performance() -> Dict[str, Any]:
    """Loads model performance metrics from the ML pipeline eval_metrics.json."""
    try:
        if os.path.exists(EVAL_METRICS_PATH):
            with open(EVAL_METRICS_PATH, "r", encoding="utf-8") as f:
                metrics = json.load(f)
            return {
                "accuracy": metrics.get("accuracy"),
                "f1_score": metrics.get("f1_macro"),
                "precision": metrics.get("precision_macro"),
                "recall": metrics.get("recall_macro"),
                "roc_auc": metrics.get("roc_auc"),
                "model_type": "GradientBoosting / XGBoost Classifier",
                "xai_status": "Active (SHAP & LIME)"
            }
    except Exception:
        pass
    return {
        "accuracy": None,
        "f1_score": None,
        "precision": None,
        "recall": None,
        "roc_auc": None,
        "model_type": "GradientBoosting / XGBoost Classifier",
        "xai_status": "Active (SHAP & LIME)"
    }

class AnalyticsService:
    @staticmethod
    async def get_user_dashboard_analytics(db: AsyncSession, user_id: str) -> Dict[str, Any]:
        stmt_assess = select(StressAssessment).where(StressAssessment.user_id == user_id).order_by(StressAssessment.created_at.desc())
        res_assess = await db.execute(stmt_assess)
        assessments = list(res_assess.scalars().all())
        
        stmt_pred = select(Prediction).where(Prediction.user_id == user_id).order_by(Prediction.created_at.desc())
        res_pred = await db.execute(stmt_pred)
        predictions = list(res_pred.scalars().all())
        
        total_assessments = len(assessments)
        latest_stress_level = predictions[0].stress_level if predictions else "Normal"
        
        avg_pss = float(sum(a.total_pss for a in assessments) / total_assessments) if total_assessments > 0 else 0.0
        avg_hrv = float(sum(a.hrv_sdnn for a in assessments) / total_assessments) if total_assessments > 0 else 0.0
        avg_sleep = float(sum(a.sleep_hours for a in assessments) / total_assessments) if total_assessments > 0 else 0.0
        
        stress_counts = {"Low": 0, "Moderate": 0, "High": 0, "Severe": 0}
        for p in predictions:
            if p.stress_level in stress_counts:
                stress_counts[p.stress_level] += 1
                
        # Map predictions to assessment timeline
        pred_map = {p.assessment_id: p for p in predictions}
        timeline = []
        for a in reversed(assessments[:15]):
            p = pred_map.get(a.id)
            timeline.append({
                "date": a.created_at.strftime("%b %d"),
                "stress_level": p.stress_level if p else "Moderate",
                "total_pss": a.total_pss,
                "heart_rate": a.heart_rate,
                "hrv_sdnn": a.hrv_sdnn,
                "sleep_hours": a.sleep_hours,
                "confidence_score": p.confidence_score if p else 0.85
            })
            
        # Facial expression analysis summary
        stmt_facial = select(FacialAnalysis).where(FacialAnalysis.user_id == user_id).order_by(FacialAnalysis.created_at.desc())
        res_facial = await db.execute(stmt_facial)
        facial = list(res_facial.scalars().all())
        latest_facial = facial[0] if facial else None
        facial_levels = {"Low": 0, "Moderate": 0, "High": 0, "Severe": 0}
        for f in facial:
            if f.stress_level in facial_levels:
                facial_levels[f.stress_level] += 1

        return {
            "total_assessments": total_assessments,
            "latest_stress_level": latest_stress_level,
            "average_pss_score": round(avg_pss, 1),
            "average_hrv_sdnn": round(avg_hrv, 1),
            "average_sleep_hours": round(avg_sleep, 1),
            "stress_distribution": stress_counts,
            "timeline_trends": timeline,
            "total_facial_analyses": len(facial),
            "latest_facial_emotion": latest_facial.dominant_emotion if latest_facial else None,
            "latest_facial_stress_level": latest_facial.stress_level if latest_facial else None,
            "latest_facial_stress_score": latest_facial.stress_score if latest_facial else None,
            "facial_stress_distribution": facial_levels,
        }

    @staticmethod
    async def get_admin_system_analytics(db: AsyncSession) -> Dict[str, Any]:
        users_count = await db.scalar(select(func.count(User.id)))
        assess_count = await db.scalar(select(func.count(StressAssessment.id)))
        pred_count = await db.scalar(select(func.count(Prediction.id)))

        stmt_preds = select(Prediction.stress_level, func.count(Prediction.id)).group_by(Prediction.stress_level)
        res_preds = await db.execute(stmt_preds)
        breakdown = dict(res_preds.all())

        since = datetime.now(timezone.utc) - timedelta(days=7)
        active_stmt = select(func.count(func.distinct(StressAssessment.user_id))).where(
            StressAssessment.created_at >= since
        )
        active_assess = await db.scalar(active_stmt)
        active_pred_stmt = select(func.count(func.distinct(Prediction.user_id))).where(
            Prediction.created_at >= since
        )
        active_pred = await db.scalar(active_pred_stmt)
        active_facial_stmt = select(func.count(func.distinct(FacialAnalysis.user_id))).where(
            FacialAnalysis.created_at >= since
        )
        active_facial = await db.scalar(active_facial_stmt)

        active_users_7d = max(
            active_assess or 0, active_pred or 0, active_facial or 0
        )

        return {
            "total_users": users_count or 0,
            "total_assessments": assess_count or 0,
            "total_predictions": pred_count or 0,
            "total_facial_analyses": await db.scalar(select(func.count(FacialAnalysis.id))) or 0,
            "system_stress_breakdown": breakdown,
            "active_users_7d": active_users_7d,
            "model_performance_summary": _load_model_performance()
        }
