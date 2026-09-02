"""
Analytics API Endpoints
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.core.database import get_db
from backend.app.models.user import User
from backend.app.schemas.analytics import AnalyticsOverviewResponse, AdminAnalyticsResponse
from backend.app.api.v1.endpoints.auth import get_current_user
from backend.app.api.v1.deps import verify_admin
from backend.app.services.analytics_service import AnalyticsService

router = APIRouter()

@router.get("/user", response_model=AnalyticsOverviewResponse)
async def get_user_analytics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await AnalyticsService.get_user_dashboard_analytics(db, current_user.id)

@router.get("/admin", response_model=AdminAnalyticsResponse)
async def get_admin_analytics(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(verify_admin)
):
    return await AnalyticsService.get_admin_system_analytics(db)
