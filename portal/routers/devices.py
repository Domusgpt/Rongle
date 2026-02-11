"""
Device router — CRUD for Rongle hardware units.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..dependencies import get_current_user
from ..models import Device, Subscription, User
from ..schemas import (
    DeviceCreateRequest,
    DeviceDetailResponse,
    DeviceResponse,
    DeviceSettingsUpdate,
)

router = APIRouter(prefix="/devices", tags=["devices"])


@router.get("/", response_model=list[DeviceResponse])
async def list_devices(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all devices owned by the current user."""
    result = await db.execute(
        select(Device).where(Device.user_id == user.id).order_by(Device.created_at.desc())
    )
    return result.scalars().all()


@router.post("/", response_model=DeviceDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_device(
    body: DeviceCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Register a new Rongle device."""
    # Enforce subscription device limit
    sub_result = await db.execute(select(Subscription).where(Subscription.user_id == user.id))
    sub = sub_result.scalar_one_or_none()
    if sub is not None and sub.max_devices > 0:
        device_count_result = await db.execute(
            select(Device).where(Device.user_id == user.id)
        )
        device_count = len(device_count_result.scalars().all())
        if device_count >= sub.max_devices:
            raise HTTPException(
                status_code=403,
                detail=f"Device limit reached ({sub.max_devices}) for your {sub.tier} plan. Upgrade to add more.",
            )

    device = Device(
        user_id=user.id,
        name=body.name,
        hardware_type=body.hardware_type,
    )
    db.add(device)
    await db.commit()
    await db.refresh(device)
    return device


@router.get("/{device_id}", response_model=DeviceDetailResponse)
async def get_device(
    device_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get detailed info for a specific device (includes API key)."""
    device = await _get_user_device(device_id, user.id, db)
    return device


@router.patch("/{device_id}/settings", response_model=DeviceDetailResponse)
async def update_device_settings(
    device_id: str,
    body: DeviceSettingsUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update device-specific operator settings."""
    device = await _get_user_device(device_id, user.id, db)

    current = json.loads(device.settings_json) if device.settings_json else {}
    updates = body.model_dump(exclude_none=True)
    current.update(updates)
    device.settings_json = json.dumps(current)

    await db.commit()
    await db.refresh(device)
    return device


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_device(
    device_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove a device registration."""
    device = await _get_user_device(device_id, user.id, db)
    await db.delete(device)
    await db.commit()


@router.post("/{device_id}/regenerate-key", response_model=DeviceDetailResponse)
async def regenerate_device_key(
    device_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Regenerate the device API key (invalidates the old one)."""
    import secrets
    device = await _get_user_device(device_id, user.id, db)
    device.api_key = f"rng_{secrets.token_urlsafe(32)}"
    await db.commit()
    await db.refresh(device)
    return device


@router.post("/{device_id}/heartbeat")
async def device_heartbeat(
    device_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update the last-seen timestamp for a device."""
    device = await _get_user_device(device_id, user.id, db)
    device.last_seen = datetime.now(timezone.utc)
    device.is_online = True
    await db.commit()
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
async def _get_user_device(device_id: str, user_id: str, db: AsyncSession) -> Device:
    result = await db.execute(
        select(Device).where(Device.id == device_id, Device.user_id == user_id)
    )
    device = result.scalar_one_or_none()
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    return device
