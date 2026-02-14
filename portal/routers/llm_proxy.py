"""
LLM proxy router — all VLM queries go through here for metering.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..dependencies import get_current_user
from ..models import User
from ..schemas import LLMQueryRequest, LLMQueryResponse
from ..services.llm_service import LLMService, QuotaExceededError

router = APIRouter(prefix="/llm", tags=["llm"])


@router.post("/query", response_model=LLMQueryResponse)
async def llm_query(
    body: LLMQueryRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Proxy a VLM query through the portal.

    The device sends its prompt + optional screenshot here. The portal
    appends the Gemini API key, forwards the request, records usage,
    and returns the result. Devices never see the raw API key.
    """
    svc = LLMService(db)

    try:
        result = await svc.query(
            user_id=user.id,
            prompt=body.prompt,
            image_base64=body.image_base64,
            device_id=body.device_id,
            model=body.model,
        )
    except QuotaExceededError as exc:
        raise HTTPException(status_code=429, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    return LLMQueryResponse(**result)
