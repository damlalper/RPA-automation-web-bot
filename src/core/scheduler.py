"""Task scheduler with APScheduler integration."""

from datetime import datetime
from typing import Any, Callable

from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED, EVENT_JOB_MISSED
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from src.monitoring.logger import get_logger

logger = get_logger(__name__)


class TaskScheduler:
    """Scheduler for periodic and cron-based tasks."""

    def __init__(self) -> None:
        """Initialize task scheduler."""
        self._scheduler = AsyncIOScheduler(
            job_defaults={
                "coalesce": True,
                "max_instances": 3,
                "misfire_grace_time": 60,
            }
        )
        self._jobs: dict[str, dict[str, Any]] = {}
        self._setup_listeners()

    def _setup_listeners(self) -> None:
        """Setup event listeners for job monitoring."""

        def on_job_executed(event):
            logger.info(f"Job executed | id={event.job_id}")

        def on_job_error(event):
            logger.error(f"Job error | id={event.job_id} | error={event.exception}")

        def on_job_missed(event):
            logger.warning(f"Job missed | id={event.job_id}")

        self._scheduler.add_listener(on_job_executed, EVENT_JOB_EXECUTED)
        self._scheduler.add_listener(on_job_error, EVENT_JOB_ERROR)
        self._scheduler.add_listener(on_job_missed, EVENT_JOB_MISSED)

    def start(self) -> None:
        """Start the scheduler."""
        if not self._scheduler.running:
            self._scheduler.start()
            logger.info("Scheduler started")

    def stop(self) -> None:
        """Stop the scheduler."""
        if self._scheduler.running:
            self._scheduler.shutdown()
            logger.info("Scheduler stopped")

    def add_interval_job(
        self,
        job_id: str,
        func: Callable,
        seconds: int | None = None,
        minutes: int | None = None,
        hours: int | None = None,
        args: tuple | None = None,
        kwargs: dict | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> str:
        """Add interval-based job.

        Args:
            job_id: Unique job identifier
            func: Function to execute
            seconds: Interval in seconds
            minutes: Interval in minutes
            hours: Interval in hours
            args: Function arguments
            kwargs: Function keyword arguments
            start_date: When to start
            end_date: When to stop

        Returns:
            Job ID
        """
        trigger = IntervalTrigger(
            seconds=seconds,
            minutes=minutes,
            hours=hours,
            start_date=start_date,
            end_date=end_date,
        )

        self._scheduler.add_job(
            func,
            trigger=trigger,
            id=job_id,
            args=args or (),
            kwargs=kwargs or {},
            replace_existing=True,
        )

        self._jobs[job_id] = {
            "type": "interval",
            "seconds": seconds,
            "minutes": minutes,
            "hours": hours,
            "func": func.__name__,
        }

        logger.info(f"Added interval job | id={job_id} | interval={seconds}s/{minutes}m/{hours}h")
        return job_id

    def add_cron_job(
        self,
        job_id: str,
        func: Callable,
        cron_expression: str | None = None,
        year: int | str | None = None,
        month: int | str | None = None,
        day: int | str | None = None,
        week: int | str | None = None,
        day_of_week: int | str | None = None,
        hour: int | str | None = None,
        minute: int | str | None = None,
        second: int | str | None = None,
        args: tuple | None = None,
        kwargs: dict | None = None,
    ) -> str:
        """Add cron-based job.

        Args:
            job_id: Unique job identifier
            func: Function to execute
            cron_expression: Cron expression (alternative to individual fields)
            year: Year
            month: Month (1-12)
            day: Day of month (1-31)
            week: Week (1-53)
            day_of_week: Day of week (0-6 or mon-sun)
            hour: Hour (0-23)
            minute: Minute (0-59)
            second: Second (0-59)
            args: Function arguments
            kwargs: Function keyword arguments

        Returns:
            Job ID
        """
        if cron_expression:
            trigger = CronTrigger.from_crontab(cron_expression)
        else:
            trigger = CronTrigger(
                year=year,
                month=month,
                day=day,
                week=week,
                day_of_week=day_of_week,
                hour=hour,
                minute=minute,
                second=second,
            )

        self._scheduler.add_job(
            func,
            trigger=trigger,
            id=job_id,
            args=args or (),
            kwargs=kwargs or {},
            replace_existing=True,
        )

        self._jobs[job_id] = {
            "type": "cron",
            "expression": cron_expression or f"{minute} {hour} {day} {month} {day_of_week}",
            "func": func.__name__,
        }

        logger.info(f"Added cron job | id={job_id}")
        return job_id

    def remove_job(self, job_id: str) -> bool:
        """Remove a scheduled job.

        Args:
            job_id: Job ID to remove

        Returns:
            True if removed
        """
        try:
            self._scheduler.remove_job(job_id)
            self._jobs.pop(job_id, None)
            logger.info(f"Removed job | id={job_id}")
            return True
        except Exception as e:
            logger.warning(f"Failed to remove job {job_id}: {e}")
            return False

    def pause_job(self, job_id: str) -> bool:
        """Pause a job.

        Args:
            job_id: Job ID to pause

        Returns:
            True if paused
        """
        try:
            self._scheduler.pause_job(job_id)
            logger.info(f"Paused job | id={job_id}")
            return True
        except Exception as e:
            logger.warning(f"Failed to pause job {job_id}: {e}")
            return False

    def resume_job(self, job_id: str) -> bool:
        """Resume a paused job.

        Args:
            job_id: Job ID to resume

        Returns:
            True if resumed
        """
        try:
            self._scheduler.resume_job(job_id)
            logger.info(f"Resumed job | id={job_id}")
            return True
        except Exception as e:
            logger.warning(f"Failed to resume job {job_id}: {e}")
            return False

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        """Get job information.

        Args:
            job_id: Job ID

        Returns:
            Job info dict or None
        """
        job = self._scheduler.get_job(job_id)
        if job:
            return {
                "id": job.id,
                "name": job.name,
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger),
                **self._jobs.get(job_id, {}),
            }
        return None

    def get_all_jobs(self) -> list[dict[str, Any]]:
        """Get all scheduled jobs.

        Returns:
            List of job info dicts
        """
        jobs = []
        for job in self._scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger),
                **self._jobs.get(job.id, {}),
            })
        return jobs

    def run_job_now(self, job_id: str) -> bool:
        """Run a job immediately.

        Args:
            job_id: Job ID to run

        Returns:
            True if triggered
        """
        job = self._scheduler.get_job(job_id)
        if job:
            job.modify(next_run_time=datetime.now())
            logger.info(f"Triggered immediate run | id={job_id}")
            return True
        return False

    @property
    def is_running(self) -> bool:
        """Check if scheduler is running.

        Returns:
            True if running
        """
        return self._scheduler.running

    def __enter__(self) -> "TaskScheduler":
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.stop()


# Convenience functions for common schedules
def every_minutes(minutes: int) -> dict[str, int]:
    """Create interval config for every N minutes.

    Args:
        minutes: Interval in minutes

    Returns:
        Config dict
    """
    return {"minutes": minutes}


def every_hours(hours: int) -> dict[str, int]:
    """Create interval config for every N hours.

    Args:
        hours: Interval in hours

    Returns:
        Config dict
    """
    return {"hours": hours}


def daily_at(hour: int, minute: int = 0) -> dict[str, Any]:
    """Create cron config for daily execution.

    Args:
        hour: Hour (0-23)
        minute: Minute (0-59)

    Returns:
        Config dict
    """
    return {"hour": hour, "minute": minute}


def weekly_on(day_of_week: str, hour: int = 0, minute: int = 0) -> dict[str, Any]:
    """Create cron config for weekly execution.

    Args:
        day_of_week: Day (mon, tue, wed, thu, fri, sat, sun)
        hour: Hour (0-23)
        minute: Minute (0-59)

    Returns:
        Config dict
    """
    return {"day_of_week": day_of_week, "hour": hour, "minute": minute}
