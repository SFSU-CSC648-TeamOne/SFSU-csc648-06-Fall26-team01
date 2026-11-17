from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, JSON, String, Integer, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

class ProgramBaseline(Base):
    __tablename__ = "program_baselines"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    program_slug: Mapped[str] = mapped_column(String(20), index=True)

    attempt_id: Mapped[str] = mapped_column(String(36), unique=True)

    results: Mapped[list] = mapped_column(JSON)

    # newly added on 11-16-26
    schema_version: Mapped[int] = mapped_column(Integer, default=2, server_default="1")
    bodyweight_kg: Mapped[Optional[Decimal]] = mapped_column(Numeric(6,2))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )