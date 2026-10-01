from fastapi import APIRouter

from app.api.routes import formations, organizations


api_router = APIRouter()
api_router.include_router(organizations.router)
api_router.include_router(formations.router)
