"""Aggregates every route module under the versioned API prefix."""

from fastapi import APIRouter

from app.api.routes import (
    analytics,
    assistant,
    audit,
    auth,
    citizens,
    documents,
    grievances,
    projects,
    sabha,
    schemes,
    villages,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(villages.router)
api_router.include_router(citizens.router)
api_router.include_router(schemes.router)
api_router.include_router(grievances.router)
api_router.include_router(projects.router)
api_router.include_router(documents.router)
api_router.include_router(sabha.router)
api_router.include_router(analytics.router)
api_router.include_router(assistant.router)
api_router.include_router(audit.router)
