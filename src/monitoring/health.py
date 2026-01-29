"""System health monitoring."""

import asyncio
import os
import platform
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from src.core.config import settings
from src.database.connection import get_db_context
from src.monitoring.logger import get_logger

logger = get_logger(__name__)


@dataclass
class HealthStatus:
    """Health status for a component."""

    name: str
    status: str  # healthy, unhealthy, degraded
    message: str | None = None
    latency_ms: float | None = None
    details: dict[str, Any] | None = None


class HealthMonitor:
    """Monitors system health."""

    def __init__(self) -> None:
        """Initialize health monitor."""
        self._checks: dict[str, callable] = {}
        self._last_results: dict[str, HealthStatus] = {}
        self._running = False

    def register_check(self, name: str, check_func: callable) -> None:
        """Register a health check.

        Args:
            name: Check name
            check_func: Function that returns HealthStatus
        """
        self._checks[name] = check_func
        logger.debug(f"Registered health check: {name}")

    async def run_check(self, name: str) -> HealthStatus:
        """Run a specific health check.

        Args:
            name: Check name

        Returns:
            Health status
        """
        if name not in self._checks:
            return HealthStatus(name=name, status="unknown", message="Check not found")

        start = datetime.utcnow()
        try:
            check_func = self._checks[name]
            if asyncio.iscoroutinefunction(check_func):
                result = await check_func()
            else:
                result = check_func()

            latency = (datetime.utcnow() - start).total_seconds() * 1000
            result.latency_ms = latency

        except Exception as e:
            result = HealthStatus(
                name=name,
                status="unhealthy",
                message=str(e),
            )

        self._last_results[name] = result
        return result

    async def run_all_checks(self) -> dict[str, HealthStatus]:
        """Run all registered health checks.

        Returns:
            Dictionary of check results
        """
        results = {}
        for name in self._checks:
            results[name] = await self.run_check(name)
        return results

    def get_overall_status(self) -> str:
        """Get overall system health status.

        Returns:
            Overall status (healthy, degraded, unhealthy)
        """
        if not self._last_results:
            return "unknown"

        statuses = [r.status for r in self._last_results.values()]

        if all(s == "healthy" for s in statuses):
            return "healthy"
        elif any(s == "unhealthy" for s in statuses):
            return "unhealthy"
        return "degraded"

    async def start_monitoring(self, interval: int = 60) -> None:
        """Start periodic health monitoring.

        Args:
            interval: Check interval in seconds
        """
        self._running = True
        logger.info(f"Starting health monitoring | interval={interval}s")

        while self._running:
            try:
                await self.run_all_checks()
                overall = self.get_overall_status()
                logger.debug(f"Health check complete | status={overall}")
            except Exception as e:
                logger.error(f"Health monitoring error: {e}")

            await asyncio.sleep(interval)

    def stop_monitoring(self) -> None:
        """Stop periodic health monitoring."""
        self._running = False
        logger.info("Stopped health monitoring")

    def get_report(self) -> dict[str, Any]:
        """Get full health report.

        Returns:
            Health report dictionary
        """
        return {
            "status": self.get_overall_status(),
            "timestamp": datetime.utcnow().isoformat(),
            "checks": {
                name: {
                    "status": result.status,
                    "message": result.message,
                    "latency_ms": result.latency_ms,
                    "details": result.details,
                }
                for name, result in self._last_results.items()
            },
        }


# Default health checks
def check_database() -> HealthStatus:
    """Check database connectivity.

    Returns:
        Database health status
    """
    try:
        with get_db_context() as db:
            db.execute("SELECT 1")
        return HealthStatus(
            name="database",
            status="healthy",
            details={"type": "sqlite" if settings.is_sqlite else "postgresql"},
        )
    except Exception as e:
        return HealthStatus(
            name="database",
            status="unhealthy",
            message=str(e),
        )


def check_disk_space() -> HealthStatus:
    """Check available disk space.

    Returns:
        Disk space health status
    """
    try:
        import shutil

        path = settings.data_dir
        total, used, free = shutil.disk_usage(path)

        free_gb = free / (1024**3)
        used_percent = (used / total) * 100

        status = "healthy"
        if used_percent > 90:
            status = "unhealthy"
        elif used_percent > 80:
            status = "degraded"

        return HealthStatus(
            name="disk_space",
            status=status,
            details={
                "free_gb": round(free_gb, 2),
                "used_percent": round(used_percent, 2),
            },
        )
    except Exception as e:
        return HealthStatus(
            name="disk_space",
            status="unknown",
            message=str(e),
        )


def check_memory() -> HealthStatus:
    """Check memory usage.

    Returns:
        Memory health status
    """
    try:
        import psutil

        memory = psutil.virtual_memory()
        used_percent = memory.percent

        status = "healthy"
        if used_percent > 90:
            status = "unhealthy"
        elif used_percent > 80:
            status = "degraded"

        return HealthStatus(
            name="memory",
            status=status,
            details={
                "used_percent": round(used_percent, 2),
                "available_gb": round(memory.available / (1024**3), 2),
            },
        )
    except ImportError:
        return HealthStatus(
            name="memory",
            status="unknown",
            message="psutil not installed",
        )
    except Exception as e:
        return HealthStatus(
            name="memory",
            status="unknown",
            message=str(e),
        )


def get_system_info() -> dict[str, Any]:
    """Get system information.

    Returns:
        System info dictionary
    """
    return {
        "platform": platform.system(),
        "platform_version": platform.version(),
        "python_version": platform.python_version(),
        "processor": platform.processor(),
        "hostname": platform.node(),
    }


# Create default health monitor
health_monitor = HealthMonitor()
health_monitor.register_check("database", check_database)
health_monitor.register_check("disk_space", check_disk_space)
health_monitor.register_check("memory", check_memory)
