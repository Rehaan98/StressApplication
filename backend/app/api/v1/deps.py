"""
Shared API Dependencies
"""

from fastapi import Depends, HTTPException, status
from backend.app.models.user import User, UserRole
from backend.app.api.v1.endpoints.auth import get_current_user

def verify_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.ADMIN.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role privileges required.")
    return user