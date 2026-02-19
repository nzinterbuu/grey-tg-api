import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from models.tenant import Base


class Message(Base):
    """Message table for storing incoming and outbound messages."""

    __tablename__ = "message"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenant.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    direction: Mapped[str] = mapped_column(String(8), nullable=False)  # "in" = inbound, "out" = outbound
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="sent")  # e.g. sent, delivered, read, failed
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    message_id: Mapped[int] = mapped_column(BigInteger, nullable=False, name="telegram_message_id")
    phone_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
