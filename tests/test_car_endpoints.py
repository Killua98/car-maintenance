from datetime import date

from fastapi import HTTPException
from sqlmodel import Session, select

from backend.api.routes.car import (
    create_car,
    create_recommendations_batch,
    delete_car,
    get_car_details,
    get_car_maintenance_categories,
    get_cars,
)
from backend.data_models.car import ModelCar, ModelCarCreate
from backend.data_models.mileage import ModelMileage
from backend.data_models.recommended_maintenance import (
    ModelRecommendedMaintenance,
    ModelRecommendedMaintenanceBase,
)

from . import BackendTestCase


class CarEndpointTests(BackendTestCase):
    def test_list_cars_returns_cars_in_id_order(self) -> None:
        first_id = self.create_test_car(vin="FIRST-VIN")
        second_id = self.create_test_car(vin="SECOND-VIN", plate_nr="TEST456")
        other_user = self.create_test_user("other@example.com")
        with Session(self.engine) as session:
            create_car(
                ModelCarCreate(
                    vin="OTHER-USER-VIN-2",
                    plate_nr="OTHER456",
                    producer="Test",
                    model="Auto",
                    first_registration=date(2020, 1, 1),
                ),
                session,
                other_user,
            )

        with Session(self.engine) as session:
            cars = get_cars(session, self.owner)

        self.assertEqual([car.id for car in cars], [first_id, second_id])

    def test_create_car_generates_id_and_does_not_require_car_id(self) -> None:
        car_data = ModelCarCreate(
            vin="GENERATED-ID-VIN",
            plate_nr="AUTO123",
            producer="Test",
            model="Auto",
            first_registration=date(2023, 4, 12),
        )

        with Session(self.engine) as session:
            result = create_car(car_data, session, self.owner)
            car = session.get(ModelCar, result["id"])

        self.assertIsInstance(result["id"], int)
        self.assertIsNotNone(car)
        self.assertNotIn("car_id", ModelCarCreate.model_fields)

    def test_create_car_persists_initial_mileage_and_returns_details(self) -> None:
        car_data = ModelCarCreate(
            vin="CREATED-VIN",
            plate_nr="NEW123",
            producer="Test",
            model="Auto",
            first_registration=date(2023, 4, 12),
        )

        with Session(self.engine) as session:
            result = create_car(car_data, session, self.owner, initial_mileage=42_500)
            car_id = result["id"]
            details = get_car_details(car_id, session, self.owner)
            mileage_records = session.exec(
                select(ModelMileage).where(ModelMileage.car_id == car_id)
            ).all()

        self.assertEqual(details["id"], car_id)
        self.assertEqual(details["plate_nr"], "NEW123")
        self.assertEqual(details["current_mileage"], 42_500)
        self.assertEqual(len(mileage_records), 1)
        self.assertEqual(mileage_records[0].mileage, 42_500)
        self.assertEqual(mileage_records[0].date, date.today())

    def test_get_car_details_raises_not_found_for_unknown_car(self) -> None:
        with (
            Session(self.engine) as session,
            self.assertRaises(HTTPException) as raised,
        ):
            get_car_details(999, session, self.owner)

        self.assertEqual(raised.exception.status_code, 404)

    def test_user_cannot_access_or_delete_another_users_car(self) -> None:
        other_user = self.create_test_user("other-owner@example.com")
        other_car_id = self.create_test_car(vin="PRIVATE-CAR")

        with Session(self.engine) as session:
            with self.assertRaises(HTTPException) as get_error:
                get_car_details(other_car_id, session, other_user)
            with self.assertRaises(HTTPException) as delete_error:
                delete_car(other_car_id, session, other_user)
            car = session.get(ModelCar, other_car_id)

        self.assertEqual(get_error.exception.status_code, 404)
        self.assertEqual(delete_error.exception.status_code, 404)
        self.assertIsNotNone(car)

    def test_recommendation_batch_persists_month_only_and_kilometer_only_items(
        self,
    ) -> None:
        car_id = self.create_test_car(vin="RECOMMENDATION-VIN")
        recommendations = [
            ModelRecommendedMaintenanceBase(
                category="revisione",
                description="Revisione",
                target_mileage=None,
                target_months=24,
            ),
            ModelRecommendedMaintenanceBase(
                category="cambio_olio",
                description="Cambio olio",
                target_mileage=15_000,
                target_months=None,
            ),
        ]

        with Session(self.engine) as session:
            result = create_recommendations_batch(
                car_id, recommendations, session, self.owner
            )
            saved = session.exec(
                select(ModelRecommendedMaintenance).where(
                    ModelRecommendedMaintenance.car_id == car_id
                )
            ).all()
            categories = get_car_maintenance_categories(car_id, session, self.owner)

        self.assertEqual(result["message"], "Raccomandazioni salvate con successo")
        self.assertEqual(len(saved), 2)
        self.assertIsNone(saved[0].target_mileage)
        self.assertEqual(saved[0].target_months, 24)
        self.assertEqual(saved[1].target_mileage, 15_000)
        self.assertIsNone(saved[1].target_months)
        self.assertEqual(
            {item["category"] for item in categories},
            {"revisione", "cambio_olio"},
        )
        self.assertTrue(all(item["is_custom"] for item in categories))

    def test_recommendation_batch_raises_not_found_for_unknown_car(self) -> None:
        with (
            Session(self.engine) as session,
            self.assertRaises(HTTPException) as raised,
        ):
            create_recommendations_batch(999, [], session, self.owner)

        self.assertEqual(raised.exception.status_code, 404)

    def test_delete_car_removes_related_recommendations_and_mileage(self) -> None:
        car_id = self.create_test_car(vin="DELETE-VIN")
        recommendation = ModelRecommendedMaintenanceBase(
            category="revisione",
            target_months=24,
        )
        with Session(self.engine) as session:
            create_recommendations_batch(car_id, [recommendation], session, self.owner)
            result = delete_car(car_id, session, self.owner)
            saved_recommendations = session.exec(
                select(ModelRecommendedMaintenance).where(
                    ModelRecommendedMaintenance.car_id == car_id
                )
            ).all()

        self.assertEqual(result["message"], "Veicolo eliminato con successo")
        self.assertEqual(saved_recommendations, [])

    def test_delete_unknown_car_raises_not_found(self) -> None:
        with (
            Session(self.engine) as session,
            self.assertRaises(HTTPException) as raised,
        ):
            delete_car(999, session, self.owner)

        self.assertEqual(raised.exception.status_code, 404)
