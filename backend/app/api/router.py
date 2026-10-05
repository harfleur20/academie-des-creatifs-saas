from fastapi import APIRouter

from app.api.routes import academic, admin, assignments, auth, billing, commerce, formations, notifications, onboarding, organizations, pdf_lessons, planning, public_school, sso, support, workspace


api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(sso.router)
api_router.include_router(admin.router)
api_router.include_router(organizations.router)
api_router.include_router(formations.router)
api_router.include_router(notifications.router)
api_router.include_router(onboarding.router)
api_router.include_router(workspace.router)
api_router.include_router(planning.router)
api_router.include_router(assignments.router)
api_router.include_router(academic.router)
api_router.include_router(pdf_lessons.router)
api_router.include_router(billing.router)
api_router.include_router(public_school.router)
api_router.include_router(commerce.router)
api_router.include_router(support.router)
