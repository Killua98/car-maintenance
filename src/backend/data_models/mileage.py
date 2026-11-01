from typing import TYPE_CHECKING

from sqlalchemy.orm import Mapped, relationship
from sqlmodel import Field, Relationship, SQLModel

from .custom_types import DataItaliana

if TYPE_CHECKING:
    from .car import ModelCar


class ModelMileageBase(SQLModel):
    date: DataItaliana
    mileage: float


class ModelMileage(ModelMileageBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    car_id: int = Field(foreign_key="car.id", index=True)

    car: Mapped[ModelCar] = Relationship(
        sa_relationship=relationship("ModelCar", back_populates="historic_mileages")
    )
