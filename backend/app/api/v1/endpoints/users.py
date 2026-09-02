"""
User Management Endpoints
"""

from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.core.database import get_db
from backend.app.models.user import User
from backend.app.schemas.user import UserResponse, UserUpdate, PasswordChangeRequest
from backend.app.api.v1.deps import verify_admin
from backend.app.api.v1.endpoints.auth import get_current_user
from backend.app.services.user_service import UserService

router = APIRouter()

@router.get("/", response_model=List[UserResponse])
async def list_users(
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(verify_admin)
):
    return await UserService.list_all_users(db, skip, limit)

@router.put("/me", response_model=UserResponse)
async def update_own_profile(
    updates: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await UserService.update_profile(db, current_user, updates)

@router.post("/me/password", status_code=204)
async def change_own_password(
    req: PasswordChangeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    await UserService.change_password(db, current_user, req.current_password, req.new_password)