"""
SQLAlchemy ORM models for the Rongle Portal.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return uuid.uuid4().hex


def _device_key() -> str:
    return f"rng_{secrets.token_urlsafe(32)}"


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------
class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    # Relationships
    devices: Mapped[list[Device]] = relationship(back_populates="owner", cascade="all, delete-orphan")
    subscription: Mapped[Subscription | None] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")
    usage_records: Mapped[list[UsageRecord]] = relationship(back_populates="user", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# Device (a single Rongle hardware unit)
# ---------------------------------------------------------------------------
class Device(Base):
    __tablename__ = "devices"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    hardware_type: Mapped[str] = mapped_column(String(50), default="pi_zero_2w")
    api_key: Mapped[str] = mapped_column(String(64), default=_device_key, unique=True)
    is_online: Mapped[bool] = mapped_column(Boolean, default=False)
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    # Device-specific configuration (JSON blob)
    settings_json: Mapped[str] = mapped_column(Text, default="{}")
    # Device-specific policy override (JSON blob, same schema as allowlist.json)
    policy_json: Mapped[str] = mapped_column(Text, default="{}")

    # Relationships
    owner: Mapped[User] = relationship(back_populates="devices")
    audit_entries: Mapped[list[AuditEntry]] = relationship(back_populates="device", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# Subscription (billing tier)
# ---------------------------------------------------------------------------
class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False)
    tier: Mapped[str] = mapped_column(String(20), default="free")  # free | starter | pro | enterprise
    llm_quota_monthly: Mapped[int] = mapped_column(Integer, default=100)  # API calls per month
    llm_used_this_month: Mapped[int] = mapped_column(Integer, default=0)
    max_devices: Mapped[int] = mapped_column(Integer, default=1)
    billing_cycle_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    # Relationships
    user: Mapped[User] = relationship(back_populates="subscription")


# ---------------------------------------------------------------------------
# UsageRecord (per-call LLM metering)
# ---------------------------------------------------------------------------
class UsageRecord(Base):
    __tablename__ = "usage_records"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    device_id: Mapped[str | None] = mapped_column(ForeignKey("devices.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)  # "vlm_query", "describe_screen", etc.
    model: Mapped[str] = mapped_column(String(100), default="")
    tokens_input: Mapped[int] = mapped_column(Integer, default=0)
    tokens_output: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)


# ---------------------------------------------------------------------------
# AuditEntry (synced from device Merkle chain)
# ---------------------------------------------------------------------------
class AuditEntry(Base):
    __tablename__ = "audit_entries"
    __table_args__ = (
        UniqueConstraint("device_id", "sequence", name="uq_device_sequence"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id"), nullable=False, index=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp: Mapped[float] = mapped_column(Float, nullable=False)
    timestamp_iso: Mapped[str] = mapped_column(String(30), default="")
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    action_detail: Mapped[str] = mapped_column(Text, default="")
    screenshot_hash: Mapped[str] = mapped_column(String(64), default="")
    previous_hash: Mapped[str] = mapped_column(String(64), default="")
    entry_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_verdict: Mapped[str] = mapped_column(String(20), default="")

    # Relationships
    device: Mapped[Device] = relationship(back_populates="audit_entries")
