"""
Prediction API Endpoints
"""

from typing import List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from backend.app.core.database import get_db
from backend.app.models.prediction import Prediction
from backend.app.models.user import User
from backend.app.schemas.prediction import PredictionRequest, PredictionResponse
from backend.app.api.v1.endpoints.auth import get_current_user
from backend.app.services.ml_service import MLService

router = APIRouter()

@router.get("/", response_model=List[PredictionResponse])
async def list_user_predictions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(10, ge=1, le=100)
):
    stmt = (
        select(Prediction)
        .where(Prediction.user_id == current_user.id)
        .order_by(Prediction.created_at.desc())
        .limit(limit)
    )
    res = await db.execute(stmt)
    return res.scalars().all()

@router.get("/{prediction_id}", response_model=PredictionResponse)
async def get_prediction_detail(
    prediction_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await MLService.get_prediction_detail(db, prediction_id, current_user.id)

@router.post("/", response_model=PredictionResponse, status_code=status.HTTP_201_CREATED)
async def run_stress_prediction(
    req: PredictionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    prediction, ml_out = await MLService.run_prediction_for_assessment(db, current_user.id, req.assessment_id)
    
    return PredictionResponse(
        id=prediction.id,
        assessment_id=prediction.assessment_id,
        user_id=prediction.user_id,
        predicted_class_id=prediction.predicted_class_id,
        stress_level=prediction.stress_level,
        confidence_score=prediction.confidence_score,
        class_probabilities=prediction.class_probabilities,
        created_at=prediction.created_at,
        shap_explanation=ml_out.get("shap_explanation"),
        lime_explanation=ml_out.get("lime_explanation"),
        rag_interventions=ml_out.get("rag_interventions")
    )
