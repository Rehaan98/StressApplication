"""
Stress Assessments API Endpoints
"""

from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.core.database import get_db
from backend.app.models.user import User
from backend.app.schemas.assessment import StressAssessmentCreate, StressAssessmentResponse
from backend.app.api.v1.endpoints.auth import get_current_user
from backend.app.services.stress_service import StressService

router = APIRouter()

@router.post("/", response_model=StressAssessmentResponse, status_code=status.HTTP_201_CREATED)
async def create_stress_assessment(
    data: StressAssessmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await StressService.create_assessment(db, current_user.id, data)

@router.get("/", response_model=List[StressAssessmentResponse])
async def list_user_assessments(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await StressService.get_user_assessments(db, current_user.id, limit)

@router.get("/{assessment_id}", response_model=StressAssessmentResponse)
async def get_assessment(
    assessment_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await StressService.get_assessment_by_id(db, assessment_id, current_user.id)
