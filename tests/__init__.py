import unittest
import uuid
from datetime import date

from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from backend.api.routes.car import create_car
from backend.data_models.car import ModelCar, ModelCarCreate
from backend.data_models.maintenance import ModelMaintenance
from backend.data_models.mileage import ModelMileage
from backend.data_models.recommended_maintenance import ModelRecommendedMaintenance
from backend.data_models.users import User

API_BASE_URL = "/api/v1"
API_URLS = {
    "login": f"{API_BASE_URL}/login/access-token",
    "users": f"{API_BASE_URL}/users",
    "cars": f"{API_BASE_URL}/cars",
    "maintenance": f"{API_BASE_URL}/maintenance",
    "mileage": f"{API_BASE_URL}/mileage",
}


def make_domain_car(
    *,
    first_registration: date = date(2020, 1, 1),
    historic_mileages: list[ModelMileage] | None = None,
    maintenance_history: list[ModelMaintenance] | None = None,
    recommendations: list[ModelRecommendedMaintenance] | None = None,
) -> ModelCar:
    return ModelCar(
        vin="DOMAIN-TEST-VIN",
        plate_nr="DOMAIN123",
        producer="Test",
        model="Auto",
        first_registration=first_registration,
        user_id=uuid.uuid4(),
        historic_mileages=historic_mileages or [],
        maintenance_history=maintenance_history or [],
        custom_maintenance_recommendations=recommendations or [],
    )


class BackendTestCase(unittest.TestCase):
    """Shared isolated SQLite fixtures for backend tests."""

    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        SQLModel.metadata.create_all(self.engine)
        with Session(self.engine) as session:
            self.owner = User(
                email="owner@example.com",
                hashed_password="test-password-hash",
            )
            session.add(self.owner)
            session.commit()
            session.refresh(self.owner)

    def tearDown(self) -> None:
        self.engine.dispose()

    def create_test_user(self, email: str) -> User:
        with Session(self.engine) as session:
            user = User(email=email, hashed_password="test-password-hash")
            session.add(user)
            session.commit()
            session.refresh(user)
            return user

    def create_test_car(
        self,
        *,
        producer: str = "Test",
        model: str = "Auto",
        vin: str = "TEST-VIN",
        plate_nr: str = "TEST123",
        first_registration: date = date(2020, 1, 1),
        initial_mileage: float = 1_000,
    ) -> int:
        with Session(self.engine) as session:
            result = create_car(
                ModelCarCreate(
                    producer=producer,
                    model=model,
                    vin=vin,
                    plate_nr=plate_nr,
                    first_registration=first_registration,
                ),
                session,
                self.owner,
            )
            car_id = result["id"]
            car = session.get(ModelCar, car_id)
            self.assertIsNotNone(car)
            assert car is not None
            car.historic_mileages.append(
                ModelMileage(
                    date=first_registration,
                    mileage=initial_mileage,
                    car_id=car_id,
                )
            )
            session.add(car)
            session.commit()

        self.assertIsInstance(car_id, int)
        return car_id
