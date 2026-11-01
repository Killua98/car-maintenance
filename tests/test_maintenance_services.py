import unittest
from datetime import date, datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from backend.data_models.maintenance import ModelMaintenance
from backend.data_models.mileage import ModelMileage
from backend.data_models.recommended_maintenance import ModelRecommendedMaintenance
from backend.services.maintenance_services import MaintenanceService

from . import make_domain_car

TODAY = date(2026, 10, 11)
FIXED_NOW = datetime(2026, 10, 11, tzinfo=ZoneInfo("Europe/Rome"))
SERVICE_DATETIME = "backend.services.maintenance_services.datetime"


class MaintenanceServiceTests(unittest.TestCase):
    @patch(SERVICE_DATETIME)
    def test_classifies_due_soon_overdue_and_up_to_date_items(
        self, datetime_mock
    ) -> None:
        datetime_mock.now.return_value = FIXED_NOW
        car = make_domain_car(
            first_registration=date(2026, 7, 11),
            historic_mileages=[ModelMileage(date=TODAY, mileage=12_000, car_id=1)],
            recommendations=[
                ModelRecommendedMaintenance(
                    category="km_due_soon",
                    target_mileage=15_000,
                    car_id=1,
                ),
                ModelRecommendedMaintenance(
                    category="months_due_soon",
                    target_months=6,
                    car_id=1,
                ),
                ModelRecommendedMaintenance(
                    category="km_overdue",
                    target_mileage=11_999,
                    car_id=1,
                ),
                ModelRecommendedMaintenance(
                    category="months_overdue",
                    target_months=2,
                    car_id=1,
                ),
                ModelRecommendedMaintenance(
                    category="up_to_date",
                    target_mileage=20_000,
                    target_months=12,
                    description="Controllo periodico",
                    car_id=1,
                ),
            ],
        )

        report = MaintenanceService(car).check_maintenance_status()

        self.assertEqual(
            {item.category for item in report.due_soon},
            {"km_due_soon", "months_due_soon"},
        )
        self.assertEqual(
            {item.category for item in report.overdue},
            {"km_overdue", "months_overdue"},
        )
        self.assertEqual([item.category for item in report.up_to_date], ["up_to_date"])
        self.assertEqual(report.up_to_date[0].km_left, 8_000)
        self.assertEqual(report.up_to_date[0].months_left, 9)
        self.assertEqual(report.up_to_date[0].description, "Controllo periodico")

    @patch(SERVICE_DATETIME)
    def test_uses_most_recent_maintenance_for_remaining_intervals(
        self, datetime_mock
    ) -> None:
        datetime_mock.now.return_value = FIXED_NOW
        car = make_domain_car(
            first_registration=date(2020, 1, 1),
            historic_mileages=[
                ModelMileage(date=date(2024, 1, 1), mileage=10_000, car_id=1),
                ModelMileage(date=date(2025, 1, 1), mileage=15_000, car_id=1),
            ],
            maintenance_history=[
                ModelMaintenance(
                    category="cambio_olio",
                    cost=100,
                    mileage=5_000,
                    date=date(2024, 10, 11),
                    car_id=1,
                ),
                ModelMaintenance(
                    category="cambio_olio",
                    cost=125,
                    mileage=12_000,
                    date=date(2025, 10, 11),
                    car_id=1,
                ),
            ],
            recommendations=[
                ModelRecommendedMaintenance(
                    category="cambio_olio",
                    target_mileage=5_000,
                    target_months=12,
                    car_id=1,
                )
            ],
        )

        report = MaintenanceService(car).check_maintenance_status()

        self.assertEqual(len(report.overdue), 1)
        item = report.overdue[0]
        self.assertEqual(item.km_left, 2_000)
        self.assertEqual(item.months_left, 0)

    @patch(SERVICE_DATETIME)
    def test_supports_month_only_and_kilometer_only_recommendations(
        self, datetime_mock
    ) -> None:
        datetime_mock.now.return_value = FIXED_NOW
        car = make_domain_car(
            first_registration=date(2026, 7, 11),
            historic_mileages=[ModelMileage(date=TODAY, mileage=12_000, car_id=1)],
            recommendations=[
                ModelRecommendedMaintenance(
                    category="solo_mesi",
                    target_months=6,
                    car_id=1,
                ),
                ModelRecommendedMaintenance(
                    category="solo_km",
                    target_mileage=15_000,
                    car_id=1,
                ),
            ],
        )

        report = MaintenanceService(car).check_maintenance_status()
        items = {
            item.category: item
            for item in [*report.overdue, *report.due_soon, *report.up_to_date]
        }

        self.assertEqual(items["solo_mesi"].km_left, None)
        self.assertEqual(items["solo_mesi"].months_left, 3)
        self.assertEqual(items["solo_km"].km_left, 3_000)
        self.assertEqual(items["solo_km"].months_left, None)
        self.assertEqual(
            {item.category for item in report.due_soon},
            {"solo_mesi", "solo_km"},
        )

    @patch(SERVICE_DATETIME)
    def test_returns_empty_report_when_car_has_no_recommendations(
        self, datetime_mock
    ) -> None:
        datetime_mock.now.return_value = FIXED_NOW

        report = MaintenanceService(make_domain_car()).check_maintenance_status()

        self.assertEqual(report.overdue, [])
        self.assertEqual(report.due_soon, [])
        self.assertEqual(report.up_to_date, [])
