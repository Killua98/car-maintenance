from fastapi import APIRouter, HTTPException

from ...data_models.mileage import ModelMileage
from ..deps import CurrentUser, SessionDep, get_owned_car

router = APIRouter(tags=["mileage"])


@router.delete("/{mileage_id}")
def delete_mileage_record(
    mileage_id: int,
    session: SessionDep,
    current_user: CurrentUser,
):
    """Elimina uno specifico record di kilometraggio dallo storico."""
    mileage_record = session.get(ModelMileage, mileage_id)
    if mileage_record is None:
        raise HTTPException(status_code=404, detail="Intervento non trovato")

    get_owned_car(session, mileage_record.car_id, current_user)
    session.delete(mileage_record)
    session.commit()
    return {"message": "Kilometraggio eliminato con successo"}
