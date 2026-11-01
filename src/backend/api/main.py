from fastapi import APIRouter

from .routes import car, health, maintenance, mileage, users

api_router = APIRouter()
api_router.include_router(users.login_router)
api_router.include_router(car.router, prefix="/cars")
api_router.include_router(maintenance.router, prefix="/maintenance")
api_router.include_router(mileage.router, prefix="/mileage")
api_router.include_router(users.router, prefix="/users")
api_router.include_router(health.router, prefix="/health")
