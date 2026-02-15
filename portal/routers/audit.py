"""
Audit router — retrieve and sync tamper-evident logs.
"""

from __future__ import annotations

import hashlib

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..dependencies import get_current_user, get_device_by_api_key
from ..models import AuditEntry, Device, User
from ..schemas import AuditEntryResponse, AuditSyncRequest

router = APIRouter(tags=["audit"])


# ---------------------------------------------------------------------------
# User-facing: read audit log
# ---------------------------------------------------------------------------
@router.get("/devices/{device_id}/audit", response_model=list[AuditEntryResponse])
async def get_audit_log(
    device_id: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve paginated audit entries for a device, newest first."""
    # Verify ownership
    dev_result = await db.execute(
        select(Device).where(Device.id == device_id, Device.user_id == user.id)
    )
    if dev_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Device not found")

    result = await db.execute(
        select(AuditEntry)
        .where(AuditEntry.device_id == device_id)
        .order_by(AuditEntry.sequence.desc())
        .offset(offset)
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/devices/{device_id}/audit/verify")
async def verify_audit_chain(
    device_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Verify the Merkle chain integrity of a device's audit log.

    Re-computes every hash from genesis and checks linkage.
    """
    dev_result = await db.execute(
        select(Device).where(Device.id == device_id, Device.user_id == user.id)
    )
    if dev_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Device not found")

    result = await db.execute(
        select(AuditEntry)
        .where(AuditEntry.device_id == device_id)
        .order_by(AuditEntry.sequence.asc())
    )
    entries = result.scalars().all()

    if not entries:
        return {"status": "empty", "entries_verified": 0}

    prev_hash = "0" * 64
    for entry in entries:
        # Verify linkage
        if entry.previous_hash != prev_hash:
            return {
                "status": "broken",
                "broken_at_sequence": entry.sequence,
                "detail": f"previous_hash mismatch at seq {entry.sequence}",
            }
        # Recompute hash
        preimage = f"{entry.timestamp:.6f}|{entry.action}|{entry.screenshot_hash}|{entry.previous_hash}"
        expected = hashlib.sha256(preimage.encode()).hexdigest()
        if entry.entry_hash != expected:
            return {
                "status": "tampered",
                "tampered_at_sequence": entry.sequence,
                "detail": f"entry_hash mismatch at seq {entry.sequence}",
            }
        prev_hash = entry.entry_hash

    return {
        "status": "valid",
        "entries_verified": len(entries),
        "chain_head": prev_hash,
    }


# ---------------------------------------------------------------------------
# Device-facing: sync audit entries from device to portal
# ---------------------------------------------------------------------------
@router.post("/audit/sync")
async def sync_audit_entries(
    body: AuditSyncRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Receive a batch of audit entries from a device.

    Called by the device-side portal_client to upload its local
    Merkle-chain log entries to the central portal for storage
    and future verification.
    """
    # Authenticate device by API key
    dev_result = await db.execute(
        select(Device).where(Device.api_key == body.device_api_key)
    )
    device = dev_result.scalar_one_or_none()
    if device is None:
        raise HTTPException(status_code=401, detail="Invalid device API key")

    inserted = 0
    for entry_data in body.entries:
        # Skip duplicates by sequence number
        existing = await db.execute(
            select(AuditEntry)
            .where(
                AuditEntry.device_id == device.id,
                AuditEntry.sequence == entry_data.get("sequence"),
            )
        )
        if existing.scalar_one_or_none() is not None:
            continue

        audit_entry = AuditEntry(
            device_id=device.id,
            sequence=entry_data.get("sequence", 0),
            timestamp=entry_data.get("timestamp", 0.0),
            timestamp_iso=entry_data.get("timestamp_iso", ""),
            action=entry_data.get("action", ""),
            action_detail=entry_data.get("action_detail", ""),
            screenshot_hash=entry_data.get("screenshot_hash", ""),
            previous_hash=entry_data.get("previous_hash", ""),
            entry_hash=entry_data.get("entry_hash", ""),
            policy_verdict=entry_data.get("policy_verdict", ""),
        )
        db.add(audit_entry)
        inserted += 1

    await db.commit()
    return {"synced": inserted, "total_received": len(body.entries)}
