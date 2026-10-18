# user-side tables (user, user_profiles, assessments) and table linking 
# a profile to the equipment that is available to that person.

from datetime import datetime
from typing import List, Optional

from sqlalchemy import (JSON, CheckConstraint, Column, DateTime, ForeignKey, Integer,
                        String, Table, Text, func)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import ExperienceLevel, UserRole, sql_in

user_equipment = Table(
    "user_equipment",
    Base.metadata,
    Column("user_profile_id", ForeignKey("user_profiles.id", ondelete="CASCADE"), primary_key=True),
    Column("equipment_id", ForeignKey("equipment.id", ondelete="CASCADE"), primary_key=True),
)

class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint(f"role IN ({sql_in(UserRole)})", name="ck_users_role"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[Optional[str]] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(20), default=UserRole.user.value, server_default=UserRole.user.value)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    profile: Mapped[Optional["UserProfile"]] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan")
    assessments: Mapped[List["Assessment"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", order_by="Assessment.created_at.desc()")

class UserProfile(Base):
    __tablename__ = "user_profiles"
    __table_args__ = (
        CheckConstraint(f"experience_level IN ({sql_in(ExperienceLevel)})", name="ck_user_profiles_level"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    goals: Mapped[list] = mapped_column(JSON, default=list)
    experience_level: Mapped[Optional[str]] = mapped_column(String(20))
    days_per_week: Mapped[Optional[int]] = mapped_column(Integer)
    session_minutes: Mapped[Optional[int]] = mapped_column(Integer)
    physical_constraints: Mapped[Optional[str]] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped[User] = relationship(back_populates="profile")
    equipment: Mapped[List["Equipment"]] = relationship(secondary=user_equipment)

class Assessment(Base):
    __tablename__ = "assessments"
    __table_args__ = (
        CheckConstraint(f"experience_level IN ({sql_in(ExperienceLevel)})", name="ck_assessments_level"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    answers: Mapped[dict] = mapped_column(JSON)
    score: Mapped[int] = mapped_column(Integer)
    experience_level: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship(back_populates="assessments")

from app.models.catalog import Equipment