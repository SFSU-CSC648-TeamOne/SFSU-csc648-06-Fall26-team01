from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String, func
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

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )