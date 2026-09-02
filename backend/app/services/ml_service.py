"""
ML Inference & XAI Business Logic Service
"""

from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi import HTTPException, status
from backend.app.models.assessment import StressAssessment
from backend.app.models.prediction import Prediction
from backend.app.models.explainability_log import ExplainabilityLog
from backend.app.models.rag_coping_log import RAGCopingLog
from ml_engine.predict import StressPredictor

predictor_instance = StressPredictor()

class MLService:
    @staticmethod
    async def run_prediction_for_assessment(db: AsyncSession, user_id: str, assessment_id: str) -> tuple[Prediction, Dict[str, Any]]:
        stmt = select(StressAssessment).where(StressAssessment.id == assessment_id)
        res = await db.execute(stmt)
        assessment = res.scalars().first()
        
        if not assessment or assessment.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found.")
            
        raw_input = {
            "pss_q1": assessment.pss_q1, "pss_q2": assessment.pss_q2,
            "pss_q3": assessment.pss_q3, "pss_q4": assessment.pss_q4,
            "pss_q5": assessment.pss_q5, "pss_q6": assessment.pss_q6,
            "pss_q7": assessment.pss_q7, "pss_q8": assessment.pss_q8,
            "pss_q9": assessment.pss_q9, "pss_q10": assessment.pss_q10,
            "total_pss": assessment.total_pss,
            "heart_rate": assessment.heart_rate,
            "hrv_sdnn": assessment.hrv_sdnn,
            "sleep_hours": assessment.sleep_hours,
            "sleep_efficiency": assessment.sleep_efficiency,
            "physical_activity_min": assessment.physical_activity_min,
            "work_hours": assessment.work_hours,
            "screen_time_hours": assessment.screen_time_hours,
            "breaks_per_day": assessment.breaks_per_day,
            "sentiment_score": assessment.sentiment_score,
            "anxiety_score": assessment.anxiety_score
        }
        
        ml_out = predictor_instance.predict_instance(raw_input)
        
        prediction = Prediction(
            assessment_id=assessment_id,
            user_id=user_id,
            predicted_class_id=ml_out["predicted_class_id"],
            stress_level=ml_out["stress_level"],
            confidence_score=ml_out["confidence_score"],
            class_probabilities=ml_out["class_probabilities"]
        )
        db.add(prediction)
        await db.commit()
        await db.refresh(prediction)
        
        # Save XAI Log
        xai_log = ExplainabilityLog(
            prediction_id=prediction.id,
            user_id=user_id,
            shap_top_drivers=ml_out["shap_explanation"]["top_drivers"],
            lime_rules=ml_out["lime_explanation"]["lime_rules"]
        )
        db.add(xai_log)
        await db.commit()
        
        return prediction, ml_out

    @staticmethod
    async def get_prediction_by_id(db: AsyncSession, prediction_id: str, user_id: str) -> Optional[Prediction]:
        stmt = select(Prediction).where(Prediction.id == prediction_id)
        res = await db.execute(stmt)
        pred = res.scalars().first()
        if not pred or pred.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prediction record not found.")
        return pred

    @staticmethod
    async def get_prediction_detail(db: AsyncSession, prediction_id: str, user_id: str) -> Dict[str, Any]:
        """Returns a prediction enriched with its stored SHAP/LIME and RAG data."""
        pred = await MLService.get_prediction_by_id(db, prediction_id, user_id)

        xai_stmt = select(ExplainabilityLog).where(ExplainabilityLog.prediction_id == prediction_id)
        xai_res = await db.execute(xai_stmt)
        xai_log = xai_res.scalars().first()

        rag_stmt = (
            select(RAGCopingLog)
            .where(RAGCopingLog.prediction_id == prediction_id)
            .order_by(RAGCopingLog.created_at.desc())
        )
        rag_res = await db.execute(rag_stmt)
        rag_log = rag_res.scalars().first()

        return {
            "id": pred.id,
            "assessment_id": pred.assessment_id,
            "user_id": pred.user_id,
            "predicted_class_id": pred.predicted_class_id,
            "stress_level": pred.stress_level,
            "confidence_score": pred.confidence_score,
            "class_probabilities": pred.class_probabilities,
            "created_at": pred.created_at,
            "shap_explanation": {
                "predicted_class": pred.stress_level,
                "top_drivers": xai_log.shap_top_drivers if xai_log else [],
                "all_features": xai_log.shap_top_drivers if xai_log else [],
            } if xai_log else None,
            "lime_explanation": {
                "predicted_class": pred.stress_level,
                "lime_rules": xai_log.lime_rules if xai_log else [],
            } if xai_log else None,
            "rag_interventions": (
                rag_log.retrieved_interventions if rag_log else []
            ),
        }
