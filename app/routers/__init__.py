from fastapi import APIRouter

from app.routers import save, sorting

api_router = APIRouter()
api_router.include_router(save.router)
api_router.include_router(sorting.router)
