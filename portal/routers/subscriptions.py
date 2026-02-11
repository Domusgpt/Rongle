"""
Subscription router — tier management and usage reporting.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..dependencies import get_current_user
from ..models import Subscription, UsageRecord, User
from ..schemas import TIER_LIMITS, SubscriptionResponse, SubscriptionUpdateRequest

router = APIRouter(prefix="/subscription", tags=["subscription"])


@router.get("/", response_model=SubscriptionResponse)
async def get_subscription(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the current user's subscription details."""
    result = await db.execute(select(Subscription).where(Subscription.user_id == user.id))
    sub = result.scalar_one_or_none()
    if sub is None:
        raise HTTPException(status_code=404, detail="No subscription found")
    return sub


@router.put("/", response_model=SubscriptionResponse)
async def update_subscription(
    body: SubscriptionUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Change subscription tier.

    In production this would integrate with Stripe/payment processor.
    For MVP, tier changes are immediate.
    """
    result = await db.execute(select(Subscription).where(Subscription.user_id == user.id))
    sub = result.scalar_one_or_none()
    if sub is None:
        raise HTTPException(status_code=404, detail="No subscription found")

    limits = TIER_LIMITS.get(body.tier)
    if limits is None:
        raise HTTPException(status_code=400, detail=f"Unknown tier: {body.tier}")

    sub.tier = body.tier
    sub.llm_quota_monthly = limits["llm_quota_monthly"]
    sub.max_devices = limits["max_devices"]

    await db.commit()
    await db.refresh(sub)
    return sub


@router.get("/usage")
async def get_usage_summary(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get usage summary for the current billing cycle."""
    result = await db.execute(select(Subscription).where(Subscription.user_id == user.id))
    sub = result.scalar_one_or_none()
    if sub is None:
        raise HTTPException(status_code=404, detail="No subscription found")

    # Count calls this cycle
    usage_result = await db.execute(
        select(func.count(UsageRecord.id))
        .where(UsageRecord.user_id == user.id)
        .where(UsageRecord.timestamp >= sub.billing_cycle_start)
    )
    total_calls = usage_result.scalar() or 0

    # Sum tokens
    tokens_result = await db.execute(
        select(
            func.coalesce(func.sum(UsageRecord.tokens_input), 0),
            func.coalesce(func.sum(UsageRecord.tokens_output), 0),
        )
        .where(UsageRecord.user_id == user.id)
        .where(UsageRecord.timestamp >= sub.billing_cycle_start)
    )
    row = tokens_result.one()

    return {
        "tier": sub.tier,
        "billing_cycle_start": sub.billing_cycle_start.isoformat(),
        "llm_calls_used": total_calls,
        "llm_calls_quota": sub.llm_quota_monthly,
        "tokens_input_total": row[0],
        "tokens_output_total": row[1],
    }
