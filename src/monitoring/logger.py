"""Centralized logging configuration using Loguru."""

import sys
from pathlib import Path
from typing import Any

from loguru import logger

from src.core.config import settings


def setup_logging() -> None:
    """Configure Loguru logging for the application."""
    # Remove default handler
    logger.remove()

    # Console format
    console_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )

    # File format (more detailed)
    file_format = (
        "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
        "{level: <8} | "
        "{name}:{function}:{line} | "
        "{message} | "
        "{extra}"
    )

    # Add console handler
    logger.add(
        sys.stderr,
        format=console_format,
        level=settings.log_level,
        colorize=True,
        backtrace=True,
        diagnose=settings.debug,
    )

    # Add file handler for all logs
    logs_dir = settings.logs_dir
    logger.add(
        logs_dir / "rpaflow_{time:YYYY-MM-DD}.log",
        format=file_format,
        level="DEBUG",
        rotation="00:00",  # Rotate at midnight
        retention="30 days",
        compression="gz",
        serialize=False,
        backtrace=True,
        diagnose=True,
    )

    # Add separate file for errors
    logger.add(
        logs_dir / "errors_{time:YYYY-MM-DD}.log",
        format=file_format,
        level="ERROR",
        rotation="00:00",
        retention="90 days",
        compression="gz",
        backtrace=True,
        diagnose=True,
    )

    # Add JSON file for structured logging (useful for log aggregation)
    logger.add(
        logs_dir / "rpaflow_{time:YYYY-MM-DD}.json",
        format="{message}",
        level="INFO",
        rotation="00:00",
        retention="14 days",
        compression="gz",
        serialize=True,
    )

    logger.info(
        f"Logging initialized | level={settings.log_level} | env={settings.app_env.value}"
    )


def get_logger(name: str) -> Any:
    """Get a logger instance with the given name.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Configured logger instance
    """
    return logger.bind(name=name)


class LogContext:
    """Context manager for adding extra context to logs."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize with context data.

        Args:
            **kwargs: Key-value pairs to add to log context
        """
        self.context = kwargs
        self._token = None

    def __enter__(self) -> "LogContext":
        """Enter context and bind extra data."""
        self._token = logger.configure(extra=self.context)
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit context."""
        pass


def log_task_start(task_id: str, task_type: str, **extra: Any) -> None:
    """Log task start event.

    Args:
        task_id: Unique task identifier
        task_type: Type of task
        **extra: Additional context
    """
    logger.bind(task_id=task_id, task_type=task_type, **extra).info(
        f"Task started | id={task_id} | type={task_type}"
    )


def log_task_complete(
    task_id: str, task_type: str, duration: float, success: bool = True, **extra: Any
) -> None:
    """Log task completion event.

    Args:
        task_id: Unique task identifier
        task_type: Type of task
        duration: Task duration in seconds
        success: Whether task completed successfully
        **extra: Additional context
    """
    status = "SUCCESS" if success else "FAILED"
    log_func = logger.info if success else logger.error

    log_func(
        f"Task completed | id={task_id} | type={task_type} | "
        f"status={status} | duration={duration:.2f}s",
        task_id=task_id,
        task_type=task_type,
        duration=duration,
        success=success,
        **extra,
    )


def log_scraping_event(
    url: str, items_count: int, duration: float, success: bool = True, **extra: Any
) -> None:
    """Log scraping event.

    Args:
        url: Scraped URL
        items_count: Number of items scraped
        duration: Scraping duration in seconds
        success: Whether scraping was successful
        **extra: Additional context
    """
    status = "SUCCESS" if success else "FAILED"
    log_func = logger.info if success else logger.warning

    log_func(
        f"Scraping | url={url} | items={items_count} | "
        f"status={status} | duration={duration:.2f}s",
        url=url,
        items_count=items_count,
        duration=duration,
        success=success,
        **extra,
    )


def log_proxy_event(
    proxy: str, action: str, success: bool = True, response_time: float | None = None, **extra: Any
) -> None:
    """Log proxy-related event.

    Args:
        proxy: Proxy address
        action: Action performed (rotation, health_check, etc.)
        success: Whether action was successful
        response_time: Response time in seconds (for health checks)
        **extra: Additional context
    """
    status = "SUCCESS" if success else "FAILED"
    log_func = logger.info if success else logger.warning

    msg = f"Proxy {action} | proxy={proxy} | status={status}"
    if response_time is not None:
        msg += f" | response_time={response_time:.3f}s"

    log_func(msg, proxy=proxy, action=action, success=success, response_time=response_time, **extra)
