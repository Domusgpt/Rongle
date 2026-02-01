"""
User router — profile management.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import hash_password
from ..database import get_db
from ..dependencies import get_current_user
from ..models import User
from ..schemas import UserResponse, UserUpdateRequest

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    """Return the current user's profile."""
    return user


@router.patch("/me", response_model=UserResponse)
async def update_me(
    body: UserUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update current user's profile."""
    if body.display_name is not None:
        user.display_name = body.display_name
    if body.password is not None:
        user.hashed_password = hash_password(body.password)

    await db.commit()
    await db.refresh(user)
    return user
