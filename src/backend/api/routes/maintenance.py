from fastapi import APIRouter, HTTPException

from ...data_models.maintenance import ModelMaintenance
from ..deps import CurrentUser, SessionDep, get_owned_car

router = APIRouter(tags=["maintenance"])


@router.delete("/{maintenance_id}")
def delete_maintenance_record(
    maintenance_id: int,
    session: SessionDep,
    current_user: CurrentUser,
):
    """Elimina uno specifico intervento dallo storico."""
    maintenance_record = session.get(ModelMaintenance, maintenance_id)
    if maintenance_record is None:
        raise HTTPException(status_code=404, detail="Intervento non trovato")

    get_owned_car(session, maintenance_record.car_id, current_user)
    session.delete(maintenance_record)
    session.commit()
    return {"message": "Intervento eliminato con successo"}
