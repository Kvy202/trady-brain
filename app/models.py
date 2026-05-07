from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func

from app.database import Base


class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String, unique=True, index=True, nullable=False)
    device_name = Column(String, nullable=False)
    refresh_token = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_seen = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ConversationTurn(Base):
    __tablename__ = "conversation_turns"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String, index=True, nullable=False)
    role = Column(String, nullable=False)   # "user" | "assistant"
    message = Column(String, nullable=False)
    intent = Column(String, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())


class AuditLog(Base):
    """Immutable record of every trading command issued."""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String, index=True, nullable=False)
    command = Column(String, nullable=False)
    reason = Column(String, nullable=True)
    mode = Column(String, nullable=False)          # mock | real | paper | live
    outcome = Column(String, nullable=False)       # allowed | approval_required | blocked | error
    approval_id = Column(String, nullable=True)    # UUID if approval was created
    bot_response = Column(Text, nullable=True)     # JSON snapshot of bot reply (no secrets)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())


class PendingApproval(Base):
    """Short-lived approval token for risky commands."""
    __tablename__ = "pending_approvals"

    id = Column(Integer, primary_key=True, index=True)
    approval_id = Column(String, unique=True, index=True, nullable=False)  # UUID
    device_id = Column(String, index=True, nullable=False)
    command = Column(String, nullable=False)
    reason = Column(String, nullable=True)
    mode = Column(String, nullable=False)
    decision = Column(String, nullable=True)       # None | "approve" | "deny"
    decided_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class BotEvent(Base):
    """Inbound events pushed by the trading bot via webhook."""
    __tablename__ = "bot_events"

    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String, index=True, nullable=False)
    payload = Column(Text, nullable=False)         # raw JSON, no secrets
    source_ip = Column(String, nullable=True)
    verified = Column(Boolean, default=False, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
