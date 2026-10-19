# defines the data tables for exercise catalog (equpment, muscle_groups, exercises) 
# and links them with the correctprogram tables (training_prgrams, workout_sessions, and session_exercises)

from typing import List, Optional

from sqlalchemy import (CheckConstraint, Column, ForeignKey, Integer, String, Table,
                        Text, UniqueConstraint, Boolean)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import ExerciseRole, ExperienceLevel, sql_in

exercise_equipment = Table(
    "exercise_equipment",
    Base.metadata,
    Column("exercise_id", ForeignKey("exercises.id", ondelete="CASCADE"), primary_key=True),
    Column("equipment_id", ForeignKey("equipment.id", ondelete="CASCADE"), primary_key=True),
)

class Equipment(Base):
    __tablename__ = "equipment"

    id: Mapped[int] = mapped_column(primary_key=True)
    wger_id: Mapped[Optional[int]] = mapped_column(Integer, unique=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)

class MuscleGroup(Base):
    __tablename__ = "muscle_groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    wger_id: Mapped[Optional[int]] = mapped_column(Integer, unique=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)

class ExerciseMuscle(Base):
    __tablename__ = "exercise_muscles"

    exercise_id: Mapped[int] = mapped_column(ForeignKey("exercises.id", ondelete="CASCADE"), primary_key=True)
    muscle_group_id: Mapped[int] = mapped_column(ForeignKey("muscle_groups.id", ondelete="CASCADE"), primary_key=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    muscle: Mapped[MuscleGroup] = relationship()

class Exercise(Base):
    __tablename__ = "exercises"
    __table_args__ = (
        CheckConstraint(f"difficulty IS NULL OR difficulty IN ({sql_in(ExperienceLevel)})", name="ck_exercises_difficulty"),
        CheckConstraint(f"default_role IS NULL OR default_role IN ({sql_in(ExerciseRole)})", name="ck_exercises_role"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    wger_id: Mapped[Optional[int]] = mapped_column(Integer, unique=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    category: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    difficulty: Mapped[Optional[str]] = mapped_column(String(20))
    default_role: Mapped[Optional[str]] = mapped_column(String(20))
    default_minutes: Mapped[int] = mapped_column(Integer, default=5, server_default="5")
    source: Mapped[str] = mapped_column(String(20), default="manual", server_default="manual")
    license_name: Mapped[Optional[str]] = mapped_column(String(100))
    license_author: Mapped[Optional[str]] = mapped_column(String(255))

    equipment: Mapped[List[Equipment]] = relationship(secondary=exercise_equipment)
    muscle_links: Mapped[List[ExerciseMuscle]] = relationship(cascade="all, delete-orphan")

class TrainingProgram(Base):
    __tablename__ = "training_programs"
    __table_args__ = (
    CheckConstraint(f"experience_level IN ({sql_in(ExperienceLevel)})", name="ck_programs_level"),   
    )   

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    goal: Mapped[str] = mapped_column(String(100), index=True)
    experience_level: Mapped[str] = mapped_column(String(20))
    length_weeks: Mapped[int] = mapped_column(Integer)
    description: Mapped[Optional[str]] = mapped_column(Text)

    sessions: Mapped[List["WorkoutSession"]] = relationship(
        back_populates="program", cascade="all, delete-orphan", order_by="WorkoutSession.position")
    
class WorkoutSession(Base):
    __tablename__ = "workout_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    program_id: Mapped[int] = mapped_column(ForeignKey("training_programs.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    position: Mapped[int] = mapped_column(Integer)
    guidance: Mapped[Optional[str]] = mapped_column(Text)

    program: Mapped[TrainingProgram] = relationship(back_populates="sessions")
    items: Mapped[List["SessionExercise"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="SessionExercise.position")


class SessionExercise(Base):
    __tablename__ = "session_exercises"
    __table_args__ = (
        UniqueConstraint("workout_session_id", "position", name="uq_session_exercises_position"),
        CheckConstraint(f"role IN ({sql_in(ExerciseRole)})", name="ck_session_exercises_role"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    workout_session_id: Mapped[int] = mapped_column(ForeignKey("workout_sessions.id", ondelete="CASCADE"), index=True)
    exercise_id: Mapped[int] = mapped_column(ForeignKey("exercises.id"))
    position: Mapped[int] = mapped_column(Integer)
    role: Mapped[str] = mapped_column(String(20))
    sets: Mapped[Optional[int]] = mapped_column(Integer)
    reps: Mapped[Optional[int]] = mapped_column(Integer)
    minutes: Mapped[Optional[int]] = mapped_column(Integer)

    session: Mapped[WorkoutSession] = relationship(back_populates="items")
    exercise: Mapped[Exercise] = relationship()