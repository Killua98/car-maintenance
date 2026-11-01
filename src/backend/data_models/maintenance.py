from functools import total_ordering
from typing import TYPE_CHECKING

from sqlalchemy.orm import Mapped, relationship
from sqlmodel import Field, Relationship, SQLModel

from .custom_types import DataItaliana

if TYPE_CHECKING:
    from .car import ModelCar


class ModelMaintenanceBase(SQLModel):
    category: str
    cost: float
    notes: str | None = None
    mileage: float
    date: DataItaliana


class ModelMaintenance(ModelMaintenanceBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    car_id: int = Field(foreign_key="car.id", index=True)

    car: Mapped[ModelCar] = Relationship(
        sa_relationship=relationship("ModelCar", back_populates="maintenance_history")
    )


@total_ordering
class ModelMaintenanceStatusItemBase(SQLModel):
    category: str
    description: str | None = None
    km_left: float | None = None
    months_left: int | None = None

    @property
    def status(self) -> str:
        """Determina lo stato univoco della manutenzione in base a priorità logica."""
        if (self.km_left is not None and self.km_left <= 0) or (
            self.months_left is not None and self.months_left <= 0
        ):
            return "overdue"

        if (self.km_left is not None and self.km_left <= 3000) or (
            self.months_left is not None and self.months_left <= 3
        ):
            return "due_soon"

        return "up_to_date"

    def _sort_key(self):
        # Funzione di supporto per stabilire la priorità di un singolo campo:
        # - Se è None, va in fondo (infinito positivo)
        # - Se è negativo o positivo, mantiene il suo valore (i negativi saranno naturalmente minori)
        def val_key(val):
            if val is None:
                return float("inf")
            return val

        # Restituisce una tupla che confronta prima i km e poi i mesi
        return (val_key(self.km_left), val_key(self.months_left))

    def __lt__(self, other: ModelMaintenanceStatusItemBase) -> bool:
        if not isinstance(other, ModelMaintenanceStatusItemBase):
            return NotImplemented
        return self._sort_key() < other._sort_key()

    def __eq__(self, other: ModelMaintenanceStatusItemBase) -> bool:
        if not isinstance(other, ModelMaintenanceStatusItemBase):
            return NotImplemented
        return self._sort_key() == other._sort_key()


class ModelMaintenanceStatusReport(SQLModel):
    overdue: list[ModelMaintenanceStatusItemBase] = Field(default_factory=list)
    due_soon: list[ModelMaintenanceStatusItemBase] = Field(default_factory=list)
    up_to_date: list[ModelMaintenanceStatusItemBase] = Field(default_factory=list)


# class CustomMaintenanceRecommendation(MaintenanceRecommendationFields, table=True):
#    id: int | None = Field(default=None, primary_key=True)
#    car_id: int = Field(foreign_key="car.id")
#
#    car: Mapped[Car] = Relationship(
#        sa_relationship=relationship(
#            lambda: Car, back_populates="custom_maintenance_recommendations"
#        )
#    )
