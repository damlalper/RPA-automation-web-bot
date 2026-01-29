"""Health check endpoints."""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.core.config import settings
from src.database.connection import get_db

router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str
    timestamp: str
    version: str
    environment: str
    components: dict[str, Any]


class ComponentHealth(BaseModel):
    """Component health model."""

    status: str
    message: str | None = None
    latency_ms: float | None = None


@router.get("/health", response_model=HealthResponse)
async def health_check(db: Session = Depends(get_db)) -> HealthResponse:
    """Check system health.

    Returns:
        Health status of all components
    """
    components = {}

    # Database check
    try:
        db.execute("SELECT 1")
        components["database"] = {"status": "healthy", "type": "sqlite" if settings.is_sqlite else "postgresql"}
    except Exception as e:
        components["database"] = {"status": "unhealthy", "error": str(e)}

    # Overall status
    all_healthy = all(c.get("status") == "healthy" for c in components.values())

    return HealthResponse(
        status="healthy" if all_healthy else "degraded",
        timestamp=datetime.utcnow().isoformat(),
        version="1.0.0",
        environment=settings.app_env.value,
        components=components,
    )


@router.get("/health/live")
async def liveness_probe() -> dict[str, str]:
    """Kubernetes liveness probe.

    Returns:
        Simple alive response
    """
    return {"status": "alive"}


@router.get("/health/ready")
async def readiness_probe(db: Session = Depends(get_db)) -> dict[str, str]:
    """Kubernetes readiness probe.

    Returns:
        Ready status
    """
    try:
        db.execute("SELECT 1")
        return {"status": "ready"}
    except Exception:
        return {"status": "not_ready"}


@router.get("/info")
async def system_info() -> dict[str, Any]:
    """Get system information.

    Returns:
        System configuration info
    """
    return {
        "app_name": settings.app_name,
        "version": "1.0.0",
        "environment": settings.app_env.value,
        "debug": settings.debug,
        "database_type": "sqlite" if settings.is_sqlite else "postgresql",
        "worker_pool_size": settings.worker_pool_size,
        "max_concurrent": settings.worker_max_concurrent,
        "proxy_enabled": settings.proxy_enabled,
    }
