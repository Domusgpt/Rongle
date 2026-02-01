"""
Policy router — per-device allowlist management.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..dependencies import get_current_user
from ..models import Device, User
from ..schemas import PolicyResponse, PolicyUpdateRequest

router = APIRouter(prefix="/devices", tags=["policies"])


@router.get("/{device_id}/policy", response_model=PolicyResponse)
async def get_policy(
    device_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the current policy for a device."""
    device = await _get_user_device(device_id, user.id, db)
    policy = json.loads(device.policy_json) if device.policy_json else {}
    return PolicyResponse(device_id=device.id, policy=policy)


@router.put("/{device_id}/policy", response_model=PolicyResponse)
async def set_policy(
    device_id: str,
    body: PolicyUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Replace the entire policy for a device."""
    device = await _get_user_device(device_id, user.id, db)
    device.policy_json = json.dumps(body.model_dump())
    await db.commit()
    await db.refresh(device)
    policy = json.loads(device.policy_json)
    return PolicyResponse(device_id=device.id, policy=policy)


@router.patch("/{device_id}/policy", response_model=PolicyResponse)
async def patch_policy(
    device_id: str,
    body: dict,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Partially update the policy for a device (merge with existing)."""
    device = await _get_user_device(device_id, user.id, db)
    current = json.loads(device.policy_json) if device.policy_json else {}
    current.update(body)
    device.policy_json = json.dumps(current)
    await db.commit()
    await db.refresh(device)
    return PolicyResponse(device_id=device.id, policy=current)


async def _get_user_device(device_id: str, user_id: str, db: AsyncSession) -> Device:
    result = await db.execute(
        select(Device).where(Device.id == device_id, Device.user_id == user_id)
    )
    device = result.scalar_one_or_none()
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    return device
