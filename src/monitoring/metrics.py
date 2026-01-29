"""Metrics collection and aggregation."""

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from src.database.connection import get_db_context
from src.database.repository import BotMetricsRepository
from src.monitoring.logger import get_logger

logger = get_logger(__name__)


@dataclass
class MetricPoint:
    """Single metric data point."""

    name: str
    value: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    tags: dict[str, str] = field(default_factory=dict)


class MetricsCollector:
    """Collects and stores performance metrics."""

    def __init__(self, buffer_size: int = 100) -> None:
        """Initialize metrics collector.

        Args:
            buffer_size: Max metrics to buffer before flush
        """
        self._buffer: list[MetricPoint] = []
        self._buffer_size = buffer_size
        self._counters: dict[str, float] = {}
        self._gauges: dict[str, float] = {}
        self._timers: dict[str, list[float]] = {}

    def increment(self, name: str, value: float = 1.0, tags: dict[str, str] | None = None) -> None:
        """Increment a counter.

        Args:
            name: Counter name
            value: Value to add
            tags: Optional tags
        """
        key = self._make_key(name, tags)
        self._counters[key] = self._counters.get(key, 0) + value
        self._buffer_metric(name, self._counters[key], tags)

    def gauge(self, name: str, value: float, tags: dict[str, str] | None = None) -> None:
        """Set a gauge value.

        Args:
            name: Gauge name
            value: Current value
            tags: Optional tags
        """
        key = self._make_key(name, tags)
        self._gauges[key] = value
        self._buffer_metric(name, value, tags)

    def timing(self, name: str, value: float, tags: dict[str, str] | None = None) -> None:
        """Record a timing value.

        Args:
            name: Timer name
            value: Duration in seconds
            tags: Optional tags
        """
        key = self._make_key(name, tags)
        if key not in self._timers:
            self._timers[key] = []
        self._timers[key].append(value)
        self._buffer_metric(name, value, tags)

    def timer(self, name: str, tags: dict[str, str] | None = None) -> "Timer":
        """Create a timer context manager.

        Args:
            name: Timer name
            tags: Optional tags

        Returns:
            Timer context manager
        """
        return Timer(self, name, tags)

    def _make_key(self, name: str, tags: dict[str, str] | None) -> str:
        """Create unique key from name and tags.

        Args:
            name: Metric name
            tags: Metric tags

        Returns:
            Unique key
        """
        if tags:
            tag_str = ",".join(f"{k}={v}" for k, v in sorted(tags.items()))
            return f"{name}:{tag_str}"
        return name

    def _buffer_metric(self, name: str, value: float, tags: dict[str, str] | None) -> None:
        """Add metric to buffer.

        Args:
            name: Metric name
            value: Metric value
            tags: Optional tags
        """
        point = MetricPoint(name=name, value=value, tags=tags or {})
        self._buffer.append(point)

        if len(self._buffer) >= self._buffer_size:
            self.flush()

    def flush(self) -> None:
        """Flush buffered metrics to database."""
        if not self._buffer:
            return

        try:
            with get_db_context() as db:
                repo = BotMetricsRepository(db)
                for point in self._buffer:
                    repo.record_metric(
                        metric_type=point.name,
                        extra_data={"value": point.value, "tags": point.tags},
                    )
            logger.debug(f"Flushed {len(self._buffer)} metrics")
        except Exception as e:
            logger.error(f"Failed to flush metrics: {e}")
        finally:
            self._buffer.clear()

    def get_counter(self, name: str, tags: dict[str, str] | None = None) -> float:
        """Get current counter value.

        Args:
            name: Counter name
            tags: Optional tags

        Returns:
            Counter value
        """
        key = self._make_key(name, tags)
        return self._counters.get(key, 0)

    def get_gauge(self, name: str, tags: dict[str, str] | None = None) -> float | None:
        """Get current gauge value.

        Args:
            name: Gauge name
            tags: Optional tags

        Returns:
            Gauge value or None
        """
        key = self._make_key(name, tags)
        return self._gauges.get(key)

    def get_timer_stats(self, name: str, tags: dict[str, str] | None = None) -> dict[str, float] | None:
        """Get timer statistics.

        Args:
            name: Timer name
            tags: Optional tags

        Returns:
            Timer stats dict or None
        """
        key = self._make_key(name, tags)
        values = self._timers.get(key)

        if not values:
            return None

        return {
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "avg": sum(values) / len(values),
            "sum": sum(values),
        }

    def get_all_stats(self) -> dict[str, Any]:
        """Get all collected statistics.

        Returns:
            Statistics dictionary
        """
        return {
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "timers": {k: self.get_timer_stats(k) for k in self._timers},
        }

    def reset(self) -> None:
        """Reset all metrics."""
        self._counters.clear()
        self._gauges.clear()
        self._timers.clear()
        self._buffer.clear()


class Timer:
    """Context manager for timing operations."""

    def __init__(
        self,
        collector: MetricsCollector,
        name: str,
        tags: dict[str, str] | None = None,
    ) -> None:
        """Initialize timer.

        Args:
            collector: MetricsCollector instance
            name: Timer name
            tags: Optional tags
        """
        self._collector = collector
        self._name = name
        self._tags = tags
        self._start: float | None = None

    def __enter__(self) -> "Timer":
        """Start timing."""
        self._start = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Stop timing and record."""
        if self._start is not None:
            duration = time.perf_counter() - self._start
            self._collector.timing(self._name, duration, self._tags)

    @property
    def elapsed(self) -> float:
        """Get elapsed time.

        Returns:
            Elapsed seconds
        """
        if self._start is None:
            return 0.0
        return time.perf_counter() - self._start


# Global metrics collector
metrics = MetricsCollector()


# Convenience functions
def record_scraping_metric(
    task_id: str,
    items: int,
    duration: float,
    success: bool,
    pages: int = 1,
) -> None:
    """Record scraping operation metric.

    Args:
        task_id: Task ID
        items: Items scraped
        duration: Duration in seconds
        success: Whether successful
        pages: Pages scraped
    """
    tags = {"task_id": task_id, "success": str(success).lower()}

    metrics.increment("scraping.tasks", tags={"success": str(success).lower()})
    metrics.increment("scraping.items", value=items)
    metrics.increment("scraping.pages", value=pages)
    metrics.timing("scraping.duration", duration, tags=tags)

    if success:
        metrics.increment("scraping.success")
    else:
        metrics.increment("scraping.failures")


def record_proxy_metric(
    proxy: str,
    success: bool,
    response_time: float | None = None,
) -> None:
    """Record proxy usage metric.

    Args:
        proxy: Proxy address
        success: Whether request succeeded
        response_time: Response time in seconds
    """
    tags = {"success": str(success).lower()}

    metrics.increment("proxy.requests", tags=tags)

    if response_time is not None:
        metrics.timing("proxy.response_time", response_time)

    if success:
        metrics.increment("proxy.success")
    else:
        metrics.increment("proxy.failures")


def record_worker_metric(
    worker_id: str,
    state: str,
    task_duration: float | None = None,
) -> None:
    """Record worker metric.

    Args:
        worker_id: Worker ID
        state: Worker state
        task_duration: Task duration if completed
    """
    tags = {"worker_id": worker_id, "state": state}

    metrics.gauge("worker.state", 1 if state == "running" else 0, tags=tags)

    if task_duration is not None:
        metrics.timing("worker.task_duration", task_duration, tags={"worker_id": worker_id})
