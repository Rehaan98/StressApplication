"""
API v1 Router Registration
"""

from fastapi import APIRouter
from backend.app.api.v1.endpoints import (
    auth, users, stress_assessments, predictions,
    explainability, rag_interventions, analytics, admin, reports, facial, tracker
)

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(stress_assessments.router, prefix="/assessments", tags=["Stress Assessments"])
api_router.include_router(predictions.router, prefix="/predictions", tags=["Predictions & ML"])
api_router.include_router(explainability.router, prefix="/explainability", tags=["XAI Explainability"])
api_router.include_router(rag_interventions.router, prefix="/rag", tags=["RAG Coping Interventions"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["Analytics & Dashboards"])
api_router.include_router(admin.router, prefix="/admin", tags=["Admin Management"])
api_router.include_router(reports.router, prefix="/reports", tags=["Reports & Export"])
api_router.include_router(facial.router, prefix="/facial", tags=["Facial Expression Analysis"])
api_router.include_router(tracker.router, prefix="/tracker", tags=["Fitness Tracker Data"])
