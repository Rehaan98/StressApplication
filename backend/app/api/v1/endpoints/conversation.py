"""
Natural conversation bot endpoints (additive — existing /voice/*, /facial/* untouched).

POST /conversation/start            → begin a session (warm greeting)
POST /conversation/message          → one user message → supportive reply + activity
GET  /conversation/{session_id}     → session history + remembered facts
DELETE /conversation/{session_id}   → end the session warmly
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.api.v1.endpoints.auth import get_current_user
from backend.app.models.user import User
from backend.app.schemas.conversation import (
    ConversationStartRequest,
    ConversationStartResponse,
    ConversationMessageRequest,
    ConversationMessageResponse,
    ConversationHistoryResponse,
    ConversationEndResponse,
)
from backend.app.services.conversation import (
    start_conversation,
    handle_message,
    get_history,
    end_conversation,
)

router = APIRouter()


@router.post("/start", response_model=ConversationStartResponse)
async def conversation_start(
    req: ConversationStartRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        res = start_conversation(user_name=req.user_name or current_user.full_name)
        return ConversationStartResponse(
            session_id=res["session_id"],
            reply=res["reply"],
            activity=res.get("activity", "supportive_conversation"),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not start conversation: {e}",
        )


@router.post("/message", response_model=ConversationMessageResponse)
async def conversation_message(
    req: ConversationMessageRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    message = (req.message or "").strip()
    if not message:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message is empty. Please type or say something first.",
        )
    try:
        res = await handle_message(
            session_id=req.session_id,
            message=message,
            stress_context=req.stress_context.model_dump() if req.stress_context else None,
            use_llm=req.use_llm if req.use_llm is not None else True,
        )
        return ConversationMessageResponse(**res)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Unknown conversation session. Please start a new conversation.",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Conversation failed: {e}",
        )


@router.get("/{session_id}", response_model=ConversationHistoryResponse)
async def conversation_history(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        res = get_history(session_id)
        return ConversationHistoryResponse(**res)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Unknown conversation session.",
        )


@router.delete("/{session_id}", response_model=ConversationEndResponse)
async def conversation_end(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    res = end_conversation(session_id)
    return ConversationEndResponse(
        session_id=res["session_id"], reply=res["reply"], ended=True
    )
