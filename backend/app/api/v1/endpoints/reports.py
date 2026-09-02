"""
Report Export API Endpoints
"""

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.core.database import get_db
from backend.app.models.user import User
from backend.app.api.v1.endpoints.auth import get_current_user
from backend.app.services.report_service import ReportService

router = APIRouter()

@router.get("/csv")
async def download_csv_report(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    csv_data = await ReportService.generate_user_csv_report(db, current_user.id)
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=stress_assessment_report.csv"}
    )
