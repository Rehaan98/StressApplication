"""
RAG Coping Intervention Business Logic Service
"""

from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from backend.app.models.prediction import Prediction
from backend.app.models.explainability_log import ExplainabilityLog
from backend.app.models.rag_coping_log import RAGCopingLog
from ml_engine.src.rag_engine import StressRAGEngine

rag_engine_instance = StressRAGEngine()

class RAGService:
    @staticmethod
    async def get_tailored_interventions(
        db: AsyncSession,
        user_id: str,
        prediction_id: Optional[str] = None,
        query_text: str = "",
        top_k: int = 3,
        emotion: str = "",
    ) -> Dict[str, Any]:
        stress_level = "Moderate"
        top_drivers = []
        
        if prediction_id:
            stmt = select(Prediction).where(Prediction.id == prediction_id)
            res = await db.execute(stmt)
            pred = res.scalars().first()
            if pred:
                stress_level = pred.stress_level
                
                # Fetch SHAP drivers
                xai_stmt = select(ExplainabilityLog).where(ExplainabilityLog.prediction_id == prediction_id)
                xai_res = await db.execute(xai_stmt)
                xai_log = xai_res.scalars().first()
                if xai_log:
                    top_drivers = xai_log.shap_top_drivers
                    
        interventions = rag_engine_instance.retrieve_interventions(
            stress_level=stress_level,
            top_shap_drivers=top_drivers,
            user_query=query_text,
            top_k=top_k,
            emotion=emotion,
        )
        
        # Log RAG query
        rag_log = RAGCopingLog(
            user_id=user_id,
            prediction_id=prediction_id,
            query_text=query_text,
            retrieved_interventions=interventions
        )
        db.add(rag_log)
        await db.commit()
        
        return {
            "query_text": query_text,
            "stress_level": stress_level,
            "interventions": interventions
        }
