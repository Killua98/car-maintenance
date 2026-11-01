from datetime import datetime
from zoneinfo import ZoneInfo

from ..data_models.car import ModelCar
from ..data_models.maintenance import (
    ModelMaintenanceStatusItemBase,
    ModelMaintenanceStatusReport,
)
from .utils import get_months_difference


class MaintenanceService:
    def __init__(self, car: ModelCar):
        self.car = car

    def check_maintenance_status(self) -> ModelMaintenanceStatusReport:
        today = datetime.now(tz=ZoneInfo("Europe/Rome")).date()
        current_mileage = self.car.most_recent_mileage or 0

        report = ModelMaintenanceStatusReport()

        for maintenance in self.car.maintenance_recommendations:
            latest = self.car.most_recent_maintenance_by_category(
                category=maintenance.category
            )

            # Calcolo km residui
            km_left = None
            if maintenance.target_mileage is not None:
                last_mileage = latest.mileage if latest else 0
                km_left = maintenance.target_mileage - (current_mileage - last_mileage)

            # Calcolo mesi residui
            months_left = None
            if maintenance.target_months is not None:
                reference_date = latest.date if latest else self.car.first_registration
                months_since_reference = get_months_difference(today, reference_date)
                months_left = maintenance.target_months - months_since_reference

            item = ModelMaintenanceStatusItemBase(
                category=maintenance.category,
                description=maintenance.description,
                km_left=km_left,
                months_left=months_left,
            )

            getattr(report, item.status.lower()).append(item)

            [
                status_list.sort()
                for _, status_list in report
                if isinstance(status_list, list)
            ]
        return report
