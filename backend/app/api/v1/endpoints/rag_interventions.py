"""
RAG Interventions API Endpoints
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.core.database import get_db
from backend.app.models.user import User
from backend.app.schemas.rag import RAGQueryRequest, RAGCopingResponse
from backend.app.api.v1.endpoints.auth import get_current_user
from backend.app.services.rag_service import RAGService

router = APIRouter()

@router.post("/", response_model=RAGCopingResponse)
async def query_rag_coping_interventions(
    req: RAGQueryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    res = await RAGService.get_tailored_interventions(
        db=db,
        user_id=current_user.id,
        prediction_id=req.prediction_id,
        query_text=req.query_text or "",
        top_k=req.top_k,
        emotion=req.emotion or ""
    )
    return RAGCopingResponse(
        query_text=res["query_text"],
        stress_level=res["stress_level"],
        interventions=res["interventions"]
    )
