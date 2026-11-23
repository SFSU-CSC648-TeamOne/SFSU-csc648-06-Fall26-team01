"""Authenticated bodyweight measurement API."""

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Annotated
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.core.errors import ValidationFailed
from app.models.tracking import BodyweightMeasurement

router = APIRouter(
    prefix="/bodyweight-measurements",
    tags=["bodyweight"],
)


class BodyweightIn(BaseModel):
    weight_kg: Decimal = Field(gt=0, le=600, max_digits=6, decimal_places=2)
    measurement_date: date
    timezone: str = Field(min_length=1, max_length=64)
    measured_at: datetime | None = None

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError, ValueError:
            raise ValueError("Invalid IANA timezone.")
        return value


class BodyweightOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    weight_kg: Decimal
    measurement_date: date
    timezone: str | None
    measured_at: datetime | None
    created_at: datetime


@router.post(
    "",
    response_model=BodyweightOut,
    status_code=status.HTTP_201_CREATED,
)
def create_measurement(
    body: BodyweightIn,
    user: CurrentUser,
    db: DbSession,
):
    tz = ZoneInfo(body.timezone)
    now = datetime.now(timezone.utc)
    today_local = now.astimezone(tz).date()

    if body.measurement_date > today_local:
        raise ValidationFailed("Measurement date cannot be in the future.")

    if body.measured_at is not None:
        # Exact timestamps must include an offset or UTC.
        if body.measured_at.tzinfo is None or body.measured_at.utcoffset() is None:
            raise ValidationFailed("Exact measurement time must include a timezone.")

        measured_utc = body.measured_at.astimezone(timezone.utc)

        if measured_utc > now:
            raise ValidationFailed("Measurement time cannot be in the future.")

        actual_local_date = measured_utc.astimezone(tz).date()

        if actual_local_date != body.measurement_date:
            raise ValidationFailed(
                "Measurement date does not match the timestamp "
                "in the supplied timezone."
            )
    else:
        measured_utc = None

    measurement = BodyweightMeasurement(
        user_id=user.id,
        weight_kg=body.weight_kg,
        measurement_date=body.measurement_date,
        timezone=body.timezone,
        measured_at=measured_utc,
    )

    db.add(measurement)
    db.commit()
    db.refresh(measurement)

    return measurement


@router.get("", response_model=list[BodyweightOut])
def list_measurements(
    user: CurrentUser,
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=365)] = 100,
):
    statement = (
        select(BodyweightMeasurement)
        .where(BodyweightMeasurement.user_id == user.id)
        .order_by(
            BodyweightMeasurement.measurement_date.desc(),
            BodyweightMeasurement.measured_at.desc().nulls_last(),
            BodyweightMeasurement.id.desc(),
        )
        .limit(limit)
    )

    return db.scalars(statement).all()
