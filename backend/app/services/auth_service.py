"""
Authentication Service
"""

from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi import HTTPException, status
from backend.app.models.user import User, UserRole
from backend.app.schemas.user import UserCreate, UserLogin, Token, UserResponse
from backend.app.core.security import get_password_hash, verify_password, create_access_token, create_refresh_token

class AuthService:
    @staticmethod
    async def register_user(db: AsyncSession, user_in: UserCreate, role: str = UserRole.USER.value) -> Token:
        stmt = select(User).where(User.email == user_in.email)
        result = await db.execute(stmt)
        existing_user = result.scalars().first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email address is already registered."
            )
            
        hashed_pwd = get_password_hash(user_in.password)
        new_user = User(
            email=user_in.email,
            full_name=user_in.full_name,
            hashed_password=hashed_pwd,
            role=role,
            is_active=True,
            is_verified=True
        )
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        
        access_token = create_access_token(subject=new_user.id)
        refresh_token = create_refresh_token(subject=new_user.id)
        
        return Token(
            access_token=access_token,
            refresh_token=refresh_token,
            user=UserResponse.model_validate(new_user)
        )

    @staticmethod
    async def authenticate_user(db: AsyncSession, login_in: UserLogin) -> Token:
        stmt = select(User).where(User.email == login_in.email)
        result = await db.execute(stmt)
        user = result.scalars().first()
        
        if not user or not verify_password(login_in.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password."
            )
            
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is deactivated."
            )
            
        access_token = create_access_token(subject=user.id)
        refresh_token = create_refresh_token(subject=user.id)
        
        return Token(
            access_token=access_token,
            refresh_token=refresh_token,
            user=UserResponse.model_validate(user)
        )
