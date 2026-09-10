"""API Routes Package (TASK-29, Module M-04)."""
from fastapi import APIRouter

from medbridge.api.routes.health import (
    check_postgres_health,
    check_qdrant_health,
    health_router,
)
from medbridge.api.routes.messages import messages_router
from medbridge.api.routes.sessions import sessions_router

# Combined API router mounted under /api
api_router = APIRouter()
api_router.include_router(sessions_router)
api_router.include_router(messages_router)
api_router.include_router(health_router)

__all__ = [
    "api_router",
    "sessions_router",
    "messages_router",
    "health_router",
    "check_postgres_health",
    "check_qdrant_health",
]
