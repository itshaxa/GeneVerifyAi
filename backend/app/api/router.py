"""Aggregated API router mounted under the versioned prefix."""

from fastapi import APIRouter

from app.api.routes import auth, health, identities, verifications

api_router = APIRouter()
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(identities.router, prefix="/identity", tags=["identity"])
api_router.include_router(
    verifications.router, prefix="/verifications", tags=["verification"]
)
