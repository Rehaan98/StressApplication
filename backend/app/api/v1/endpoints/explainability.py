"""
Explainability (SHAP & LIME) API Endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from backend.app.core.database import get_db
from backend.app.models.user import User
from backend.app.models.prediction import Prediction
from backend.app.models.explainability_log import ExplainabilityLog
from backend.app.schemas.explainability import ExplainabilityResponse
from backend.app.api.v1.endpoints.auth import get_current_user

router = APIRouter()

@router.get("/{prediction_id}", response_model=ExplainabilityResponse)
async def get_prediction_explainability(
    prediction_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    stmt = select(ExplainabilityLog).where(ExplainabilityLog.prediction_id == prediction_id)
    res = await db.execute(stmt)
    log = res.scalars().first()
    
    if not log or log.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Explainability log not found.")
    
    pred_stmt = select(Prediction).where(Prediction.id == prediction_id)
    pred_res = await db.execute(pred_stmt)
    prediction = pred_res.scalars().first()
        
    return ExplainabilityResponse(
        prediction_id=log.prediction_id,
        predicted_class=prediction.stress_level if prediction else "Unknown",
        top_drivers=log.shap_top_drivers,
        lime_rules=log.lime_rules
    )
