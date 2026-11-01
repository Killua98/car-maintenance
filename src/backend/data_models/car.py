from __future__ import annotations

import itertools
import uuid
from datetime import date
from typing import TYPE_CHECKING, ClassVar, Protocol, TypeVar

from sqlalchemy.orm import Mapped, relationship
from sqlmodel import Field, Relationship, SQLModel

from .custom_types import DataItaliana
from .maintenance import ModelMaintenance
from .mileage import ModelMileage
from .recommended_maintenance import (
    ModelRecommendedMaintenance,
    ModelRecommendedMaintenanceBase,
)
from .standard_maintenances import STANDARD_SCHEDULES

if TYPE_CHECKING:
    from .users import User


class MileageTimelineEntry(Protocol):
    date: date
    mileage: float


TimelineEntry = TypeVar("TimelineEntry", bound=MileageTimelineEntry)


def validate_mileage_timeline[TimelineEntry: MileageTimelineEntry](
    mileages: list[TimelineEntry],
) -> list[TimelineEntry]:
    """Verifica che i chilometri non diminuiscano nel tempo."""
    sorted_mileages = sorted(mileages, key=lambda mileage: mileage.date)

    for current, next_one in itertools.pairwise(sorted_mileages):
        if next_one.date > current.date and next_one.mileage < current.mileage:
            raise ValueError(
                f"Incoerenza nei chilometri: alla data {next_one.date} "
                f"({next_one.mileage} km) non puoi avere un chilometraggio "
                f"inferiore rispetto a una data precedente ({current.date} con {current.mileage} km)."
            )

    return mileages  # TODO: Verificare che succede se una data successiva ha mileage 0


class ModelCarCreate(SQLModel):
    vin: str = Field(index=True, unique=True)
    plate_nr: str
    producer: str
    model: str
    first_registration: DataItaliana


class ModelCar(ModelCarCreate, table=True):
    __tablename__: ClassVar[str] = "car"

    id: int | None = Field(default=None, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", index=True)

    owner: Mapped[User] = Relationship(
        sa_relationship=relationship("User", back_populates="cars")
    )

    historic_mileages: Mapped[list[ModelMileage]] = Relationship(
        sa_relationship=relationship(
            "ModelMileage",
            back_populates="car",
            cascade="all, delete-orphan",
        )
    )
    maintenance_history: Mapped[list[ModelMaintenance]] = Relationship(
        sa_relationship=relationship(
            "ModelMaintenance",
            back_populates="car",
            cascade="all, delete-orphan",
        )
    )
    custom_maintenance_recommendations: Mapped[list[ModelRecommendedMaintenance]] = (
        Relationship(
            sa_relationship=relationship(
                "ModelRecommendedMaintenance",
                back_populates="car",
                cascade="all, delete-orphan",
            )
        )
    )

    @property
    def most_recent_mileage(self) -> float:
        """Restituisce il chilometraggio più recente in base alla data."""
        if not self.historic_mileages:
            return 0

        latest = max(
            self.historic_mileages,
            key=lambda mileage: (mileage.date, mileage.mileage),
        )
        return latest.mileage

    @property
    def maintenance_recommendations(self) -> list[ModelRecommendedMaintenanceBase]:
        """Unisce le raccomandazioni standard e quelle personalizzate dell'auto."""
        brand_schedules = STANDARD_SCHEDULES.get(self.producer, {})
        model_schedules = brand_schedules.get(self.model, [])
        return model_schedules + self.custom_maintenance_recommendations

    def most_recent_maintenance_by_category(
        self, category: str
    ) -> ModelMaintenance | None:
        matching_records = [
            maintenance
            for maintenance in self.maintenance_history
            if maintenance.category == category
        ]
        return max(
            matching_records,
            key=lambda maintenance: maintenance.date,
            default=None,
        )
