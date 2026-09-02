"""
Facial Expression Analysis API Endpoints

POST /facial/analyze   → analyze one webcam frame (base64 JPEG) → emotion + stress
GET  /facial/history   → user's facial analysis history (for trend charts)
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.core.database import get_db
from backend.app.models.user import User
from backend.app.schemas.facial import FacialAnalyzeRequest, FacialAnalyzeResponse, FacialHistoryResponse
from backend.app.api.v1.endpoints.auth import get_current_user
from backend.app.services.facial_service import FacialService
from backend.app.services.rag_service import RAGService

router = APIRouter()


@router.post("/analyze", response_model=FacialAnalyzeResponse)
async def analyze_facial_expression(
    req: FacialAnalyzeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await FacialService.analyze(db, current_user.id, req.image, req.source)

    # RAG: tailor coping interventions to the detected emotion + stress level
    try:
        rag = await RAGService.get_tailored_interventions(
            db=db,
            user_id=current_user.id,
            query_text=f"dominant emotion {result['dominant_emotion']}",
            emotion=result["dominant_emotion"],
            top_k=3,
        )
        result["interventions"] = rag["interventions"]
    except Exception:
        pass

    return FacialAnalyzeResponse(**result)


@router.get("/history", response_model=FacialHistoryResponse)
async def get_facial_history(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=200),
):
    return await FacialService.history(db, current_user.id, limit)
