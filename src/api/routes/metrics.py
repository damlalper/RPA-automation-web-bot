"""Metrics and monitoring endpoints."""

from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.database.connection import get_db
from src.database.repository import BotMetricsRepository, ProxyStatusRepository, TaskRepository

router = APIRouter()


class MetricsSummary(BaseModel):
    """Metrics summary response model."""

    tasks: dict[str, Any]
    proxies: dict[str, Any]
    performance: dict[str, Any]
    timestamp: str


class ProxyStats(BaseModel):
    """Proxy statistics model."""

    total: int
    healthy: int
    unhealthy: int
    avg_response_time: float | None
    total_requests: int
    success_rate: float


@router.get("/summary", response_model=MetricsSummary)
async def get_metrics_summary(db: Session = Depends(get_db)) -> MetricsSummary:
    """Get overall metrics summary.

    Args:
        db: Database session

    Returns:
        Metrics summary
    """
    task_repo = TaskRepository(db)
    proxy_repo = ProxyStatusRepository(db)
    metrics_repo = BotMetricsRepository(db)

    # Task stats
    task_stats = task_repo.get_stats()

    # Proxy stats
    all_proxies = proxy_repo.get_all()
    healthy_proxies = proxy_repo.get_active_proxies()
    total_proxy_requests = sum(p.total_requests for p in all_proxies)
    total_proxy_success = sum(p.success_count for p in all_proxies)
    avg_response_time = None
    proxies_with_time = [p for p in healthy_proxies if p.response_time]
    if proxies_with_time:
        avg_response_time = sum(p.response_time for p in proxies_with_time) / len(proxies_with_time)

    proxy_stats = {
        "total": len(all_proxies),
        "healthy": len(healthy_proxies),
        "unhealthy": len(all_proxies) - len(healthy_proxies),
        "avg_response_time": round(avg_response_time, 3) if avg_response_time else None,
        "total_requests": total_proxy_requests,
        "success_rate": (total_proxy_success / total_proxy_requests * 100) if total_proxy_requests > 0 else 0,
    }

    # Performance metrics (last 24 hours)
    since = datetime.utcnow() - timedelta(hours=24)
    scraping_stats = metrics_repo.get_aggregated_stats("scraping", since)

    return MetricsSummary(
        tasks=task_stats,
        proxies=proxy_stats,
        performance=scraping_stats,
        timestamp=datetime.utcnow().isoformat(),
    )


@router.get("/tasks")
async def get_task_metrics(
    hours: int = Query(24, ge=1, le=168),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Get task metrics for time period.

    Args:
        hours: Hours to look back
        db: Database session

    Returns:
        Task metrics
    """
    task_repo = TaskRepository(db)
    stats = task_repo.get_stats()

    return {
        "period_hours": hours,
        "stats": stats,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/proxies", response_model=ProxyStats)
async def get_proxy_metrics(db: Session = Depends(get_db)) -> ProxyStats:
    """Get proxy metrics.

    Args:
        db: Database session

    Returns:
        Proxy statistics
    """
    repo = ProxyStatusRepository(db)

    all_proxies = repo.get_all()
    healthy_proxies = repo.get_active_proxies()

    total_requests = sum(p.total_requests for p in all_proxies)
    total_success = sum(p.success_count for p in all_proxies)

    avg_response_time = None
    proxies_with_time = [p for p in healthy_proxies if p.response_time]
    if proxies_with_time:
        avg_response_time = sum(p.response_time for p in proxies_with_time) / len(proxies_with_time)

    return ProxyStats(
        total=len(all_proxies),
        healthy=len(healthy_proxies),
        unhealthy=len(all_proxies) - len(healthy_proxies),
        avg_response_time=round(avg_response_time, 3) if avg_response_time else None,
        total_requests=total_requests,
        success_rate=(total_success / total_requests * 100) if total_requests > 0 else 0,
    )


@router.get("/proxies/list")
async def list_proxies(
    active_only: bool = Query(False),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """List all proxies with their status.

    Args:
        active_only: Only return active proxies
        db: Database session

    Returns:
        List of proxies
    """
    repo = ProxyStatusRepository(db)

    if active_only:
        proxies = repo.get_active_proxies()
    else:
        proxies = repo.get_all()

    return {
        "count": len(proxies),
        "proxies": [p.to_dict() for p in proxies],
    }


@router.get("/performance")
async def get_performance_metrics(
    metric_type: str = Query("scraping"),
    hours: int = Query(24, ge=1, le=168),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Get performance metrics.

    Args:
        metric_type: Type of metric
        hours: Hours to look back
        db: Database session

    Returns:
        Performance metrics
    """
    repo = BotMetricsRepository(db)
    since = datetime.utcnow() - timedelta(hours=hours)

    stats = repo.get_aggregated_stats(metric_type, since)
    recent = repo.get_by_type(metric_type, since, limit=100)

    return {
        "metric_type": metric_type,
        "period_hours": hours,
        "summary": stats,
        "recent": [m.to_dict() for m in recent[:20]],
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/timeline")
async def get_metrics_timeline(
    hours: int = Query(24, ge=1, le=168),
    interval_minutes: int = Query(60, ge=5, le=360),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Get metrics timeline for charts.

    Args:
        hours: Hours to look back
        interval_minutes: Aggregation interval
        db: Database session

    Returns:
        Timeline data
    """
    # This would be implemented with proper time-series aggregation
    # For now, return placeholder structure
    return {
        "period_hours": hours,
        "interval_minutes": interval_minutes,
        "data_points": [],
        "timestamp": datetime.utcnow().isoformat(),
    }
