from typing import TYPE_CHECKING

from sqlalchemy.orm import Mapped, relationship
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .car import ModelCar


class ModelRecommendedMaintenanceBase(SQLModel):
    category: str
    target_mileage: float | None = None
    target_months: int | None = None
    description: str | None = None
    is_custom: bool = False


class ModelRecommendedMaintenance(ModelRecommendedMaintenanceBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    car_id: int = Field(foreign_key="car.id", index=True)

    car: Mapped[ModelCar] = Relationship(
        sa_relationship=relationship(
            "ModelCar", back_populates="custom_maintenance_recommendations"
        )
    )
