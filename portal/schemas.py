"""
Pydantic schemas for request/response validation.
"""

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(default="", max_length=100)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    refresh_token: str


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------
class UserResponse(BaseModel):
    id: str
    email: str
    display_name: str
    is_active: bool
    is_admin: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UserUpdateRequest(BaseModel):
    display_name: str | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)


# ---------------------------------------------------------------------------
# Device
# ---------------------------------------------------------------------------
class DeviceCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    hardware_type: str = Field(default="pi_zero_2w", max_length=50)


class DeviceResponse(BaseModel):
    id: str
    name: str
    hardware_type: str
    is_online: bool
    last_seen: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class DeviceDetailResponse(DeviceResponse):
    api_key: str
    settings_json: str
    policy_json: str


class DeviceSettingsUpdate(BaseModel):
    """Partial update to device settings."""
    screen_width: int | None = None
    screen_height: int | None = None
    capture_fps: int | None = None
    humanizer_jitter_sigma: float | None = None
    humanizer_overshoot: float | None = None
    vlm_model: str | None = None
    confidence_threshold: float | None = None
    max_iterations: int | None = None


# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------
class PolicyUpdateRequest(BaseModel):
    """Full policy document replacement."""
    allowed_regions: list[dict] = Field(default_factory=list)
    blocked_keystroke_patterns: list[str] = Field(default_factory=list)
    allowed_keystroke_patterns: list[str] = Field(default_factory=list)
    max_commands_per_second: float = 50.0
    allow_all_regions: bool = False
    blocked_key_combos: list[str] = Field(default_factory=list)


class PolicyResponse(BaseModel):
    device_id: str
    policy: dict

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# LLM Proxy
# ---------------------------------------------------------------------------
class LLMQueryRequest(BaseModel):
    """Request to proxy through the LLM."""
    device_id: str | None = None
    prompt: str = Field(min_length=1, max_length=10000)
    image_base64: str | None = None  # optional screenshot
    model: str | None = None


class LLMQueryResponse(BaseModel):
    result: str
    tokens_input: int
    tokens_output: int
    latency_ms: float
    remaining_quota: int


# ---------------------------------------------------------------------------
# Subscription
# ---------------------------------------------------------------------------
TIER_LIMITS = {
    "free":       {"llm_quota_monthly": 100,   "max_devices": 1},
    "starter":    {"llm_quota_monthly": 2000,  "max_devices": 3},
    "pro":        {"llm_quota_monthly": 20000, "max_devices": 10},
    "enterprise": {"llm_quota_monthly": -1,    "max_devices": -1},  # unlimited
}


class SubscriptionResponse(BaseModel):
    tier: str
    llm_quota_monthly: int
    llm_used_this_month: int
    max_devices: int
    billing_cycle_start: datetime
    expires_at: datetime | None

    model_config = {"from_attributes": True}


class SubscriptionUpdateRequest(BaseModel):
    tier: str = Field(pattern=r"^(free|starter|pro|enterprise)$")


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------
class AuditEntryResponse(BaseModel):
    sequence: int
    timestamp: float
    timestamp_iso: str
    action: str
    action_detail: str
    screenshot_hash: str
    entry_hash: str
    policy_verdict: str

    model_config = {"from_attributes": True}


class AuditSyncRequest(BaseModel):
    """Batch of audit entries from a device."""
    device_api_key: str
    entries: list[dict]


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------
class DeviceTelemetry(BaseModel):
    """Real-time telemetry from device."""
    device_id: str
    state: str  # IDLE, CALIBRATING, PERCEIVING, etc.
    cursor_x: int = 0
    cursor_y: int = 0
    fps: float = 0.0
    latency_ms: float = 0.0
    estop_active: bool = False
    chain_head: str = ""
