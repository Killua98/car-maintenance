from datetime import date

from fastapi import HTTPException
from sqlmodel import Session, select

from backend.api.routes.car import (
    create_maintenance_record,
    get_car_details,
    get_car_maintenance_history,
    get_car_mileage_history,
    update_mileage,
)
from backend.api.routes.maintenance import delete_maintenance_record
from backend.api.routes.mileage import delete_mileage_record
from backend.data_models.maintenance import ModelMaintenance, ModelMaintenanceBase
from backend.data_models.mileage import ModelMileage, ModelMileageBase
from backend.main import app

from . import API_URLS, BackendTestCase


class MaintenanceEndpointTests(BackendTestCase):
    def test_update_mileage_route_persists_current_mileage(self) -> None:
        car_id = self.create_test_car(
            vin="UPDATE-MILEAGE-VIN",
            first_registration=date(2020, 1, 1),
            initial_mileage=1_000,
        )
        mileage_data = ModelMileageBase(date=date(2024, 3, 1), mileage=5_000)
        with Session(self.engine) as session:
            result = update_mileage(car_id, mileage_data, session, self.owner)
            mileages = session.exec(
                select(ModelMileage).where(ModelMileage.car_id == car_id)
            ).all()

        route_path = f"{API_URLS['cars']}/{{car_id}}/mileage"
        self.assertIn(route_path, app.openapi()["paths"])
        self.assertIn("post", app.openapi()["paths"][route_path])
        self.assertEqual(result["message"], "Kilometraggio registrato con successo")
        self.assertIn(5_000, [item.mileage for item in mileages])

    def test_update_mileage_refreshes_current_mileage_after_same_day_maintenance(
        self,
    ) -> None:
        car_id = self.create_test_car(
            vin="SAME-DAY-MILEAGE-VIN",
            first_registration=date(2020, 1, 1),
            initial_mileage=1_000,
        )
        today = date.today()
        maintenance_data = ModelMaintenanceBase(
            category="cambio_olio",
            cost=125,
            mileage=5_000,
            date=today,
        )
        mileage_data = ModelMileageBase(date=today, mileage=6_000)

        with Session(self.engine) as session:
            create_maintenance_record(car_id, maintenance_data, session, self.owner)

        with Session(self.engine) as session:
            update_mileage(car_id, mileage_data, session, self.owner)

        with Session(self.engine) as session:
            details = get_car_details(car_id, session, self.owner)

        self.assertEqual(details["current_mileage"], 6_000)

    def test_update_mileage_rejects_decrease_on_same_day_without_writing(
        self,
    ) -> None:
        car_id = self.create_test_car(
            vin="DECREASING-MILEAGE-VIN",
            first_registration=date(2020, 1, 1),
            initial_mileage=1_000,
        )
        today = date.today()

        with Session(self.engine) as session:
            update_mileage(
                car_id,
                ModelMileageBase(date=today, mileage=6_000),
                session,
                self.owner,
            )

        with Session(self.engine) as session:
            with self.assertRaises(HTTPException) as raised:
                update_mileage(
                    car_id,
                    ModelMileageBase(date=today, mileage=5_000),
                    session,
                    self.owner,
                )
            mileages = session.exec(
                select(ModelMileage).where(ModelMileage.car_id == car_id)
            ).all()

        self.assertEqual(raised.exception.status_code, 422)
        self.assertEqual(sorted(item.mileage for item in mileages), [1_000, 6_000])

    def test_create_maintenance_persists_record_and_mileage(self) -> None:
        car_id = self.create_test_car(
            vin="MAINTENANCE-VIN",
            first_registration=date(2020, 1, 1),
            initial_mileage=1_000,
        )
        maintenance_data = ModelMaintenanceBase(
            category="cambio_olio",
            cost=125.50,
            mileage=5_000,
            date=date(2024, 3, 1),
            notes="Olio sintetico",
        )

        with Session(self.engine) as session:
            result = create_maintenance_record(
                car_id, maintenance_data, session, self.owner
            )
            maintenance = session.get(ModelMaintenance, result["id"])
            mileages = session.exec(
                select(ModelMileage).where(ModelMileage.car_id == car_id)
            ).all()

        self.assertEqual(result["message"], "Manutenzione registrata con successo")
        self.assertIsNotNone(maintenance)
        assert maintenance is not None
        self.assertEqual(maintenance.category, "cambio_olio")
        self.assertEqual(maintenance.mileage, 5_000)
        self.assertEqual(
            sorted(item.mileage for item in mileages),
            [1_000, 5_000],
        )

    def test_create_maintenance_rejects_decreasing_mileage_without_writing(
        self,
    ) -> None:
        car_id = self.create_test_car(
            vin="INVALID-MILEAGE-VIN",
            first_registration=date(2020, 1, 1),
            initial_mileage=5_000,
        )
        maintenance_data = ModelMaintenanceBase(
            category="cambio_olio",
            cost=100,
            mileage=4_000,
            date=date(2024, 3, 1),
        )

        with Session(self.engine) as session:
            with self.assertRaises(HTTPException) as raised:
                create_maintenance_record(car_id, maintenance_data, session, self.owner)
            maintenance_records = session.exec(
                select(ModelMaintenance).where(ModelMaintenance.car_id == car_id)
            ).all()
            mileages = session.exec(
                select(ModelMileage).where(ModelMileage.car_id == car_id)
            ).all()

        self.assertEqual(raised.exception.status_code, 422)
        self.assertEqual(maintenance_records, [])
        self.assertEqual(len(mileages), 1)

    def test_maintenance_history_is_sorted_newest_first(self) -> None:
        car_id = self.create_test_car(vin="HISTORY-VIN")
        earlier = ModelMaintenanceBase(
            category="intervento_1",
            cost=50,
            mileage=2_000,
            date=date(2022, 1, 1),
        )
        later = ModelMaintenanceBase(
            category="intervento_2",
            cost=75,
            mileage=3_000,
            date=date(2023, 1, 1),
        )
        with Session(self.engine) as session:
            create_maintenance_record(car_id, earlier, session, self.owner)
            create_maintenance_record(car_id, later, session, self.owner)
            history = get_car_maintenance_history(car_id, session, self.owner)

        self.assertEqual(
            [item.category for item in history],
            ["intervento_2", "intervento_1"],
        )

    def test_maintenance_and_mileage_history_raise_not_found(self) -> None:
        with Session(self.engine) as session:
            with self.assertRaises(HTTPException) as maintenance_error:
                get_car_maintenance_history(999, session, self.owner)
            with self.assertRaises(HTTPException) as mileage_error:
                get_car_mileage_history(999, session, self.owner)

        self.assertEqual(maintenance_error.exception.status_code, 404)
        self.assertEqual(mileage_error.exception.status_code, 404)

    def test_delete_maintenance_record_removes_record(self) -> None:
        car_id = self.create_test_car(vin="DELETE-MAINTENANCE-VIN")
        maintenance_data = ModelMaintenanceBase(
            category="cambio_olio",
            cost=100,
            mileage=2_000,
            date=date(2023, 1, 1),
        )
        with Session(self.engine) as session:
            created = create_maintenance_record(
                car_id, maintenance_data, session, self.owner
            )
            result = delete_maintenance_record(created["id"], session, self.owner)
            deleted = session.get(ModelMaintenance, created["id"])

        self.assertEqual(result["message"], "Intervento eliminato con successo")
        self.assertIsNone(deleted)

    def test_delete_unknown_maintenance_raises_not_found(self) -> None:
        with (
            Session(self.engine) as session,
            self.assertRaises(HTTPException) as raised,
        ):
            delete_maintenance_record(999, session, self.owner)

        self.assertEqual(raised.exception.status_code, 404)

    def test_user_cannot_delete_another_users_maintenance_or_mileage(self) -> None:
        car_id = self.create_test_car(vin="PRIVATE-HISTORY")
        maintenance_data = ModelMaintenanceBase(
            category="cambio_olio",
            cost=100,
            mileage=2_000,
            date=date(2023, 1, 1),
        )
        outsider = self.create_test_user("history-outsider@example.com")

        with Session(self.engine) as session:
            maintenance = create_maintenance_record(
                car_id, maintenance_data, session, self.owner
            )
            mileage = session.exec(
                select(ModelMileage).where(ModelMileage.car_id == car_id)
            ).first()
            assert mileage is not None and mileage.id is not None
            mileage_id = mileage.id
            with self.assertRaises(HTTPException) as maintenance_error:
                delete_maintenance_record(maintenance["id"], session, outsider)
            with self.assertRaises(HTTPException) as mileage_error:
                delete_mileage_record(mileage_id, session, outsider)

            remaining_maintenance = session.get(ModelMaintenance, maintenance["id"])
            remaining_mileage = session.get(ModelMileage, mileage_id)

        self.assertEqual(maintenance_error.exception.status_code, 404)
        self.assertEqual(mileage_error.exception.status_code, 404)
        self.assertIsNotNone(remaining_maintenance)
        self.assertIsNotNone(remaining_mileage)
