"""
Admin Management Endpoints
"""

from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.core.database import get_db
from backend.app.models.user import User
from backend.app.schemas.user import UserResponse
from backend.app.api.v1.deps import verify_admin
from backend.app.services.user_service import UserService

router = APIRouter()

@router.get("/users", response_model=List[UserResponse])
async def admin_list_users(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(verify_admin)
):
    return await UserService.list_all_users(db, skip, limit)
