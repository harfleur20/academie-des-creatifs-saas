from fastapi import APIRouter

from app.api.routes import admin, auth, billing, formations, onboarding, organizations, planning, workspace


api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(admin.router)
api_router.include_router(organizations.router)
api_router.include_router(formations.router)
api_router.include_router(onboarding.router)
api_router.include_router(workspace.router)
api_router.include_router(planning.router)
api_router.include_router(billing.router)
