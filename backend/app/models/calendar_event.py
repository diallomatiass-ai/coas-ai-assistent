import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, Text, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class CalendarEvent(Base):
    __tablename__ = "calendar_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    account_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("mail_accounts.id"))
    external_event_id: Mapped[str | None] = mapped_column(String(500))  # ID fra Google/Outlook
    provider: Mapped[str | None] = mapped_column(String(20))  # "google" | "outlook"

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Kilde (optional FK — hvad skabte dette event?)
    action_item_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("action_items.id"))
    call_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("secretary_calls.id"))

    event_type: Mapped[str] = mapped_column(String(30), default="manual")  # manual | action_item | call

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="calendar_events")
    account = relationship("MailAccount", back_populates="calendar_events")
    action_item = relationship("ActionItem", back_populates="calendar_events")
    call = relationship("SecretaryCall", back_populates="calendar_events")
