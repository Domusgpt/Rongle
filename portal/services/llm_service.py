"""
LLM proxy service — meters usage and enforces subscription quotas.

All LLM calls from devices route through here so that:
  1. API keys stay on the server (devices never see the Gemini key).
  2. Every call is metered against the user's subscription quota.
  3. We can switch providers or add caching without touching device code.
"""

from __future__ import annotations

import base64
import logging
import time
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models import Subscription, UsageRecord

logger = logging.getLogger(__name__)


class QuotaExceededError(Exception):
    """Raised when a user's monthly LLM quota is exhausted."""
    pass


class LLMService:
    """
    Proxied LLM inference with quota enforcement.

    Usage (within a route)::

        svc = LLMService(db)
        result = await svc.query(user_id, device_id, prompt, image_b64)
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._client = None

    async def query(
        self,
        user_id: str,
        prompt: str,
        image_base64: str | None = None,
        device_id: str | None = None,
        model: str | None = None,
    ) -> dict:
        """
        Execute a VLM query with quota enforcement.

        Returns dict with keys: result, tokens_input, tokens_output, latency_ms, remaining_quota.
        """
        model = model or settings.LLM_DEFAULT_MODEL

        # --- Quota check ---
        sub = await self._get_subscription(user_id)
        if sub.llm_quota_monthly > 0 and sub.llm_used_this_month >= sub.llm_quota_monthly:
            raise QuotaExceededError(
                f"Monthly LLM quota exhausted ({sub.llm_used_this_month}/{sub.llm_quota_monthly}). "
                f"Upgrade from '{sub.tier}' to continue."
            )

        # --- LLM call ---
        t0 = time.time()
        result_text, tokens_in, tokens_out = await self._call_gemini(prompt, image_base64, model)
        latency = (time.time() - t0) * 1000

        # --- Record usage ---
        sub.llm_used_this_month += 1
        record = UsageRecord(
            user_id=user_id,
            device_id=device_id,
            action="vlm_query",
            model=model,
            tokens_input=tokens_in,
            tokens_output=tokens_out,
            latency_ms=latency,
        )
        self.db.add(record)
        await self.db.commit()
        await self.db.refresh(sub)

        remaining = max(0, sub.llm_quota_monthly - sub.llm_used_this_month)
        if sub.llm_quota_monthly < 0:
            remaining = 999999  # unlimited tier

        return {
            "result": result_text,
            "tokens_input": tokens_in,
            "tokens_output": tokens_out,
            "latency_ms": round(latency, 1),
            "remaining_quota": remaining,
        }

    async def _get_subscription(self, user_id: str) -> Subscription:
        result = await self.db.execute(
            select(Subscription).where(Subscription.user_id == user_id)
        )
        sub = result.scalar_one_or_none()
        if sub is None:
            # Auto-create free tier
            sub = Subscription(user_id=user_id, tier="free", llm_quota_monthly=100, max_devices=1)
            self.db.add(sub)
            await self.db.flush()
        # Check billing cycle reset
        now = datetime.now(timezone.utc)
        if sub.billing_cycle_start and (now - sub.billing_cycle_start).days >= 30:
            sub.llm_used_this_month = 0
            sub.billing_cycle_start = now
        return sub

    async def _call_gemini(
        self,
        prompt: str,
        image_base64: str | None,
        model: str,
    ) -> tuple[str, int, int]:
        """Call Google Gemini and return (text, tokens_in, tokens_out)."""
        if not settings.GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY not configured on the portal server")

        from google import genai  # type: ignore[import-untyped]
        from google.genai import types  # type: ignore[import-untyped]

        if self._client is None:
            self._client = genai.Client(api_key=settings.GEMINI_API_KEY)

        parts = [types.Part(text=prompt)]
        if image_base64:
            image_bytes = base64.b64decode(image_base64)
            parts.append(types.Part(inline_data=types.Blob(
                mime_type="image/jpeg",
                data=image_bytes,
            )))

        response = self._client.models.generate_content(
            model=model,
            contents=[types.Content(parts=parts)],
        )

        text = response.text or ""

        # Extract token counts from response metadata if available
        tokens_in = 0
        tokens_out = 0
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            tokens_in = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
            tokens_out = getattr(response.usage_metadata, "candidates_token_count", 0) or 0

        return text, tokens_in, tokens_out
