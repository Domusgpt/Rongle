"""
Shared FastAPI dependencies — auth extraction, rate limiting.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import decode_token
from .database import get_db
from .models import Device, User


async def get_current_user(
    authorization: str = Header(..., description="Bearer <token>"),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Extract and validate the JWT from the Authorization header.

    Returns the authenticated User ORM instance.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    token = authorization[7:]
    user_id = decode_token(token, expected_type="access")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or disabled")

    return user


async def get_device_by_api_key(
    x_device_key: str = Header(..., description="Device API key"),
    db: AsyncSession = Depends(get_db),
) -> Device:
    """
    Authenticate a device by its API key (used for device-to-portal calls).
    """
    result = await db.execute(select(Device).where(Device.api_key == x_device_key))
    device = result.scalar_one_or_none()
    if device is None:
        raise HTTPException(status_code=401, detail="Invalid device API key")
    return device
