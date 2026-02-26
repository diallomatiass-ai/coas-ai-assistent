import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, Text, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SecretaryCall(Base):
    __tablename__ = "secretary_calls"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    secretary_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ai_secretaries.id"), nullable=False)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"))

    caller_name: Mapped[str | None] = mapped_column(String(255))
    caller_phone: Mapped[str | None] = mapped_column(String(50))
    caller_address: Mapped[str | None] = mapped_column(String(500))

    summary: Mapped[str] = mapped_column(Text, nullable=False)
    transcript: Mapped[str | None] = mapped_column(Text)
    required_fields_data: Mapped[dict | None] = mapped_column(JSONB)

    urgency: Mapped[str] = mapped_column(String(20), default="medium")
    status: Mapped[str] = mapped_column(String(30), default="new")
    notes: Mapped[str | None] = mapped_column(Text)

    called_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    confirmation_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    secretary = relationship("AiSecretary", back_populates="calls")
    customer = relationship("Customer", back_populates="calls")
    action_items = relationship("ActionItem", back_populates="call", cascade="all, delete-orphan")
    calendar_events = relationship("CalendarEvent", back_populates="call")
