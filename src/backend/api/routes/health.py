from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/", include_in_schema=False)
def healthcheck():
    return {"status": "ok"}
