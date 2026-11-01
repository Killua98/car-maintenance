from collections.abc import Generator
from datetime import date

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from backend.api.deps import get_db
from backend.auth.security import get_password_hash
from backend.data_models.users import User
from backend.main import app

from . import API_URLS, BackendTestCase


class AuthenticationEndpointTests(BackendTestCase):
    def setUp(self) -> None:
        super().setUp()

        def override_get_db() -> Generator[Session]:
            with Session(self.engine) as session:
                yield session

        self.original_get_db = app.dependency_overrides.get(get_db)
        app.dependency_overrides[get_db] = override_get_db
        self.addCleanup(self.restore_database_dependency)
        self.client = TestClient(app)

    def restore_database_dependency(self) -> None:
        if self.original_get_db is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = self.original_get_db

    def test_car_api_requires_a_bearer_token(self) -> None:
        response = self.client.get(f"{API_URLS['cars']}/")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.headers["www-authenticate"], "Bearer")

    def test_login_token_exposes_only_the_signed_in_users_cars(self) -> None:
        from backend.api.routes.car import create_car
        from backend.data_models.car import ModelCarCreate

        with Session(self.engine) as session:
            self.owner.hashed_password = get_password_hash("correct-password")
            session.add(self.owner)
            session.commit()
            create_car(
                ModelCarCreate(
                    vin="OWNED-CAR",
                    plate_nr="OWN123",
                    producer="Test",
                    model="Owned",
                    first_registration=date(2020, 1, 1),
                ),
                session,
                self.owner,
            )
            other_user = User(
                email="different@example.com",
                hashed_password="test-password-hash",
            )
            session.add(other_user)
            session.commit()
            session.refresh(other_user)
            create_car(
                ModelCarCreate(
                    vin="OTHER-CAR",
                    plate_nr="OTHER123",
                    producer="Test",
                    model="Other",
                    first_registration=date(2020, 1, 1),
                ),
                session,
                other_user,
            )

        token_response = self.client.post(
            API_URLS["login"],
            data={"username": "owner@example.com", "password": "correct-password"},
        )

        self.assertEqual(token_response.status_code, 200)
        access_token = token_response.json()["access_token"]
        cars_response = self.client.get(
            f"{API_URLS['cars']}/",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        self.assertEqual(cars_response.status_code, 200)
        self.assertEqual([car["vin"] for car in cars_response.json()], ["OWNED-CAR"])

    def test_create_car_endpoint_saves_initial_mileage_from_query(self) -> None:
        with Session(self.engine) as session:
            self.owner.hashed_password = get_password_hash("correct-password")
            session.add(self.owner)
            session.commit()

        token_response = self.client.post(
            API_URLS["login"],
            data={"username": "owner@example.com", "password": "correct-password"},
        )
        headers = {"Authorization": "Bearer " + token_response.json()["access_token"]}
        create_response = self.client.post(
            f"{API_URLS['cars']}/?initial_mileage=42500",
            headers=headers,
            json={
                "vin": "INITIAL-MILEAGE-VIN",
                "plate_nr": "MILEAGE123",
                "producer": "Test",
                "model": "Mileage",
                "first_registration": "2020-01-01",
            },
        )
        self.assertEqual(create_response.status_code, 200)
        car_id = create_response.json()["id"]

        details_response = self.client.get(
            f"{API_URLS['cars']}/{car_id}", headers=headers
        )
        mileage_response = self.client.get(
            f"{API_URLS['cars']}/{car_id}/mileage-history", headers=headers
        )

        self.assertEqual(details_response.json()["current_mileage"], 42_500)
        self.assertEqual(len(mileage_response.json()), 1)
        self.assertEqual(mileage_response.json()[0]["mileage"], 42_500)

    def test_superuser_can_manage_users_and_read_car_statistics(self) -> None:
        from backend.api.routes.car import create_car
        from backend.data_models.car import ModelCarCreate

        with Session(self.engine) as session:
            self.owner.is_superuser = True
            self.owner.hashed_password = get_password_hash("correct-password")
            session.add(self.owner)
            session.commit()
            create_car(
                ModelCarCreate(
                    vin="STATS-CAR",
                    plate_nr="STATS123",
                    producer="Test",
                    model="Statistics",
                    first_registration=date(2020, 1, 1),
                ),
                session,
                self.owner,
            )

        token_response = self.client.post(
            API_URLS["login"],
            data={"username": "owner@example.com", "password": "correct-password"},
        )
        self.assertEqual(token_response.status_code, 200)
        headers = {"Authorization": "Bearer " + token_response.json()["access_token"]}

        create_response = self.client.post(
            f"{API_URLS['users']}/",
            headers=headers,
            json={
                "email": "new-user@example.com",
                "password": "new-user-password",
                "full_name": "Nuovo utente",
            },
        )
        self.assertEqual(create_response.status_code, 200)
        created_user_id = create_response.json()["id"]

        statistics_response = self.client.get(
            f"{API_URLS['users']}/statistics", headers=headers
        )
        self.assertEqual(statistics_response.status_code, 200)
        statistics = statistics_response.json()
        self.assertEqual(statistics["count"], 2)
        self.assertEqual(statistics["active_users"], 2)
        self.assertEqual(statistics["total_cars"], 1)
        car_counts = {user["email"]: user["cars_count"] for user in statistics["data"]}
        self.assertEqual(
            car_counts,
            {
                "owner@example.com": 1,
                "new-user@example.com": 0,
            },
        )

        suspend_response = self.client.patch(
            f"{API_URLS['users']}/{created_user_id}",
            headers=headers,
            json={"is_active": False},
        )
        self.assertEqual(suspend_response.status_code, 200)
        updated_statistics = self.client.get(
            f"{API_URLS['users']}/statistics", headers=headers
        )
        self.assertEqual(updated_statistics.json()["active_users"], 1)
        delete_response = self.client.delete(
            f"{API_URLS['users']}/{created_user_id}", headers=headers
        )
        self.assertEqual(delete_response.status_code, 200)

    def test_regular_user_cannot_read_user_statistics(self) -> None:
        with Session(self.engine) as session:
            self.owner.hashed_password = get_password_hash("correct-password")
            session.add(self.owner)
            session.commit()

        token_response = self.client.post(
            API_URLS["login"],
            data={"username": "owner@example.com", "password": "correct-password"},
        )
        headers = {"Authorization": "Bearer " + token_response.json()["access_token"]}

        response = self.client.get(f"{API_URLS['users']}/statistics", headers=headers)

        self.assertEqual(response.status_code, 403)

    def test_regular_user_can_register_from_login_screen_endpoint(self) -> None:
        with Session(self.engine) as session:
            self.owner.is_superuser = True
            session.add(self.owner)
            session.commit()

        response = self.client.post(
            f"{API_URLS['users']}/signup",
            json={
                "email": "registered@example.com",
                "password": "registered-password",
                "full_name": "Utente registrato",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["is_superuser"])

    def test_signup_cannot_preempt_initial_superuser_setup(self) -> None:
        with Session(self.engine) as session:
            owner = session.get(User, self.owner.id)
            self.assertIsNotNone(owner)
            assert owner is not None
            session.delete(owner)
            session.commit()

        signup_response = self.client.post(
            f"{API_URLS['users']}/signup",
            json={
                "email": "early-user@example.com",
                "password": "registered-password",
            },
        )

        self.assertEqual(signup_response.status_code, 403)
        with Session(self.engine) as session:
            self.assertIsNone(session.exec(select(User)).first())

        setup_response = self.client.post(
            f"{API_URLS['users']}/setup-superuser",
            json={
                "email": "admin@example.com",
                "password": "admin-password",
            },
        )

        self.assertEqual(setup_response.status_code, 200)
        self.assertTrue(setup_response.json()["is_superuser"])

        signup_after_setup_response = self.client.post(
            f"{API_URLS['users']}/signup",
            json={
                "email": "registered@example.com",
                "password": "registered-password",
            },
        )
        self.assertEqual(signup_after_setup_response.status_code, 200)
        self.assertFalse(signup_after_setup_response.json()["is_superuser"])
