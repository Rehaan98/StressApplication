"""
User Management Business Logic Service
"""

from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi import HTTPException, status
from backend.app.models.user import User
from backend.app.schemas.user import UserResponse, UserUpdate
from backend.app.core.security import verify_password, get_password_hash

class UserService:
    @staticmethod
    async def get_user_by_id(db: AsyncSession, user_id: str) -> User:
        stmt = select(User).where(User.id == user_id)
        res = await db.execute(stmt)
        user = res.scalars().first()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User account not found.")
        return user

    @staticmethod
    async def list_all_users(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[User]:
        stmt = select(User).order_by(User.created_at.desc()).offset(skip).limit(limit)
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def update_profile(db: AsyncSession, user: User, updates: UserUpdate) -> User:
        data = updates.model_dump(exclude_unset=True)
        if not data:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No update fields provided.")
        for field, value in data.items():
            setattr(user, field, value)
        await db.commit()
        await db.refresh(user)
        return user

    @staticmethod
    async def change_password(db: AsyncSession, user: User, current_password: str, new_password: str) -> None:
        if not verify_password(current_password, user.hashed_password):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect.")
        user.hashed_password = get_password_hash(new_password)
        await db.commit()
        await db.refresh(user)