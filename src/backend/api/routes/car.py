from datetime import date
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from sqlmodel import select

from ...data_models.car import ModelCar, ModelCarCreate, validate_mileage_timeline
from ...data_models.maintenance import ModelMaintenance, ModelMaintenanceBase
from ...data_models.mileage import ModelMileage, ModelMileageBase
from ...data_models.recommended_maintenance import (
    ModelRecommendedMaintenance,
    ModelRecommendedMaintenanceBase,
)
from ...services.maintenance_services import MaintenanceService
from ..deps import CurrentUser, SessionDep, get_owned_car

router = APIRouter(tags=["cars"])


def _validate_car_record(car_record: ModelCar) -> ModelCar:
    try:
        validate_mileage_timeline(car_record.historic_mileages)
        validate_mileage_timeline(car_record.maintenance_history)
    except ValueError as error:
        raise HTTPException(
            status_code=409,
            detail=f"Dati del veicolo non coerenti: {error}",
        ) from error
    return car_record


@router.get("/")
def get_cars(session: SessionDep, current_user: CurrentUser):
    cars = session.exec(
        select(ModelCar).where(ModelCar.user_id == current_user.id)
    ).all()
    return cars


@router.post("/")
def create_car(
    car_data: ModelCarCreate,
    session: SessionDep,
    current_user: CurrentUser,
    initial_mileage: Annotated[float | None, Query(ge=0)] = None,
):
    car = ModelCar(**car_data.model_dump(), user_id=current_user.id)
    session.add(car)
    session.flush()
    if initial_mileage is not None:
        if car.id is None:
            raise RuntimeError("Il database non ha assegnato un ID al veicolo")
        session.add(
            ModelMileage(
                date=date.today(),
                mileage=initial_mileage,
                car_id=car.id,
            )
        )
    session.commit()
    session.refresh(car)

    return {"id": car.id, "message": "Veicolo creato con successo"}


@router.get("/maintenance-status")
def get_car_status(car_id: int, session: SessionDep, current_user: CurrentUser):
    car_record = get_owned_car(session, car_id, current_user)
    car = _validate_car_record(car_record)
    service = MaintenanceService(car)

    return service.check_maintenance_status()


@router.get("/{car_id}")
def get_car_details(car_id: int, session: SessionDep, current_user: CurrentUser):
    car_record = get_owned_car(session, car_id, current_user)
    car = _validate_car_record(car_record)

    return {
        "id": car.id,
        "producer": car.producer,
        "model": car.model,
        "plate_nr": car.plate_nr,
        "vin": car.vin,
        "first_registration": car.first_registration,
        "current_mileage": car.most_recent_mileage or 0,
    }


@router.post("/{car_id}/maintenance-categories")
def get_car_maintenance_categories(
    car_id: int,
    session: SessionDep,
    current_user: CurrentUser,
):
    car_record = get_owned_car(session, car_id, current_user)
    car = _validate_car_record(car_record)
    custom_categories = {
        recommendation.category
        for recommendation in car.custom_maintenance_recommendations
    }
    return [
        {
            "category": recommendation.category,
            "description": recommendation.description,
            "is_custom": recommendation.category in custom_categories,
        }
        for recommendation in car.maintenance_recommendations
    ]


@router.get("/{car_id}/maintenance-history")
def get_car_maintenance_history(
    car_id: int, session: SessionDep, current_user: CurrentUser
):
    car_record = get_owned_car(session, car_id, current_user)
    history = sorted(car_record.maintenance_history, key=lambda m: m.date, reverse=True)
    return history


@router.post("/{car_id}/maintenance")
def create_maintenance_record(
    car_id: int,
    maintenance_data: ModelMaintenanceBase,
    session: SessionDep,
    current_user: CurrentUser,
):
    car_record = get_owned_car(session, car_id, current_user)
    car = _validate_car_record(car_record)
    candidate_mileages = [
        *car.historic_mileages,
        ModelMileageBase(
            date=maintenance_data.date,
            mileage=maintenance_data.mileage,
        ),
    ]
    try:
        validate_mileage_timeline(candidate_mileages)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    maintenance = ModelMaintenance(**maintenance_data.model_dump(), car_id=car_id)
    session.add(maintenance)

    new_mileage_record = ModelMileage(
        date=maintenance.date,
        mileage=maintenance.mileage,
        car_id=car_id,
    )
    session.add(new_mileage_record)

    session.commit()
    session.refresh(maintenance)

    return {"message": "Manutenzione registrata con successo", "id": maintenance.id}


@router.get("/{car_id}/mileage-history")
def get_car_mileage_history(
    car_id: int, session: SessionDep, current_user: CurrentUser
):
    car_record = get_owned_car(session, car_id, current_user)
    _validate_car_record(car_record)

    history = sorted(car_record.historic_mileages, key=lambda m: m.date, reverse=True)
    return history


@router.delete("/{car_id}")
def delete_car(car_id: int, session: SessionDep, current_user: CurrentUser):
    """Elimina un veicolo e tutti i dati correlati (grazie al cascade)."""
    car_record = get_owned_car(session, car_id, current_user)
    session.delete(car_record)
    session.commit()
    return {"message": "Veicolo eliminato con successo"}


@router.post("/{car_id}/mileage")
def update_mileage(
    car_id: int,
    mileage_data: ModelMileageBase,
    session: SessionDep,
    current_user: CurrentUser,
):
    car_record = get_owned_car(session, car_id, current_user)
    car = _validate_car_record(car_record)

    existing_mileages = [*car.historic_mileages, *car.maintenance_history]
    latest_mileage = max(
        existing_mileages,
        key=lambda mileage: (mileage.date, mileage.mileage),
        default=None,
    )
    if (
        latest_mileage is not None
        and mileage_data.date >= latest_mileage.date
        and mileage_data.mileage < latest_mileage.mileage
    ):
        raise HTTPException(
            status_code=422,
            detail="Il chilometraggio inserito non può essere inferiore all'ultimo registrato.",
        )

    candidate_mileages = [
        *existing_mileages,
        ModelMileageBase(
            date=mileage_data.date,
            mileage=mileage_data.mileage,
        ),
    ]
    try:
        validate_mileage_timeline(candidate_mileages)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    mileage = ModelMileage(**mileage_data.model_dump(), car_id=car_id)
    session.add(mileage)

    session.commit()
    session.refresh(mileage)

    return {"message": "Kilometraggio registrato con successo", "id": mileage.id}


@router.post("/{car_id}/recommendations/batch")
def create_recommendations_batch(
    car_id: int,
    recommendations: list[ModelRecommendedMaintenanceBase],
    session: SessionDep,
    current_user: CurrentUser,
):
    get_owned_car(session, car_id, current_user)

    for rec_data in recommendations:
        rec = ModelRecommendedMaintenance(**rec_data.model_dump(), car_id=car_id)
        session.add(rec)

    session.commit()
    return {"message": "Raccomandazioni salvate con successo"}
