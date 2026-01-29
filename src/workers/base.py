"""Base worker implementation."""

import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import uuid4

from src.automation.browser import BrowserManager
from src.core.config import settings
from src.database.models import Task, TaskStatus
from src.monitoring.logger import get_logger, log_task_complete, log_task_start

logger = get_logger(__name__)


class WorkerState(str, Enum):
    """Worker state."""

    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class WorkerStats:
    """Worker statistics."""

    tasks_completed: int = 0
    tasks_failed: int = 0
    total_duration: float = 0.0
    last_task_at: float | None = None
    errors: list[str] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        """Calculate success rate.

        Returns:
            Success rate percentage
        """
        total = self.tasks_completed + self.tasks_failed
        if total == 0:
            return 0.0
        return (self.tasks_completed / total) * 100

    @property
    def avg_duration(self) -> float:
        """Calculate average task duration.

        Returns:
            Average duration in seconds
        """
        total = self.tasks_completed + self.tasks_failed
        if total == 0:
            return 0.0
        return self.total_duration / total

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "tasks_completed": self.tasks_completed,
            "tasks_failed": self.tasks_failed,
            "success_rate": round(self.success_rate, 2),
            "avg_duration": round(self.avg_duration, 2),
            "total_duration": round(self.total_duration, 2),
            "recent_errors": self.errors[-5:],
        }


class BaseWorker(ABC):
    """Base worker class for executing tasks."""

    def __init__(
        self,
        worker_id: str | None = None,
        use_browser: bool = True,
        browser_headless: bool | None = None,
    ) -> None:
        """Initialize worker.

        Args:
            worker_id: Unique worker identifier
            use_browser: Whether worker needs browser
            browser_headless: Headless mode (uses settings if None)
        """
        self.worker_id = worker_id or str(uuid4())[:8]
        self.use_browser = use_browser
        self.browser_headless = browser_headless if browser_headless is not None else settings.selenium_headless

        self._state = WorkerState.IDLE
        self._stats = WorkerStats()
        self._current_task: Task | None = None
        self._browser: BrowserManager | None = None

    @property
    def state(self) -> WorkerState:
        """Get worker state.

        Returns:
            Current worker state
        """
        return self._state

    @property
    def stats(self) -> WorkerStats:
        """Get worker statistics.

        Returns:
            Worker statistics
        """
        return self._stats

    @property
    def is_available(self) -> bool:
        """Check if worker is available for tasks.

        Returns:
            True if available
        """
        return self._state == WorkerState.IDLE

    @property
    def browser(self) -> BrowserManager | None:
        """Get browser manager.

        Returns:
            BrowserManager or None
        """
        return self._browser

    def start(self) -> None:
        """Start the worker."""
        if self._state == WorkerState.RUNNING:
            logger.warning(f"Worker {self.worker_id} already running")
            return

        logger.info(f"Starting worker {self.worker_id}")

        if self.use_browser:
            self._browser = BrowserManager(headless=self.browser_headless)
            self._browser.start()

        self._state = WorkerState.IDLE
        logger.info(f"Worker {self.worker_id} started")

    def stop(self) -> None:
        """Stop the worker."""
        logger.info(f"Stopping worker {self.worker_id}")

        if self._browser:
            self._browser.stop()
            self._browser = None

        self._state = WorkerState.STOPPED
        logger.info(f"Worker {self.worker_id} stopped | stats={self._stats.to_dict()}")

    def pause(self) -> None:
        """Pause the worker."""
        if self._state == WorkerState.RUNNING:
            logger.warning(f"Cannot pause worker {self.worker_id} while task is running")
            return
        self._state = WorkerState.PAUSED
        logger.info(f"Worker {self.worker_id} paused")

    def resume(self) -> None:
        """Resume the worker."""
        if self._state == WorkerState.PAUSED:
            self._state = WorkerState.IDLE
            logger.info(f"Worker {self.worker_id} resumed")

    async def execute(self, task: Task) -> bool:
        """Execute a task.

        Args:
            task: Task to execute

        Returns:
            True if successful
        """
        if not self.is_available:
            logger.warning(f"Worker {self.worker_id} not available | state={self._state}")
            return False

        self._state = WorkerState.RUNNING
        self._current_task = task
        start_time = time.time()

        log_task_start(
            task_id=task.id,
            task_type=task.task_type,
            worker_id=self.worker_id,
        )

        try:
            result = await self.run_task(task)
            duration = time.time() - start_time

            self._stats.tasks_completed += 1
            self._stats.total_duration += duration
            self._stats.last_task_at = time.time()

            log_task_complete(
                task_id=task.id,
                task_type=task.task_type,
                duration=duration,
                success=True,
                worker_id=self.worker_id,
            )

            return result

        except Exception as e:
            duration = time.time() - start_time
            error_msg = str(e)

            self._stats.tasks_failed += 1
            self._stats.total_duration += duration
            self._stats.errors.append(error_msg)
            self._state = WorkerState.ERROR

            log_task_complete(
                task_id=task.id,
                task_type=task.task_type,
                duration=duration,
                success=False,
                error=error_msg,
                worker_id=self.worker_id,
            )

            logger.error(f"Worker {self.worker_id} task failed: {e}")
            return False

        finally:
            self._current_task = None
            if self._state == WorkerState.RUNNING:
                self._state = WorkerState.IDLE

    @abstractmethod
    async def run_task(self, task: Task) -> bool:
        """Run the actual task logic.

        Args:
            task: Task to run

        Returns:
            True if successful
        """
        pass

    def __enter__(self) -> "BaseWorker":
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.stop()


class ScrapingWorker(BaseWorker):
    """Worker specialized for scraping tasks."""

    def __init__(self, **kwargs) -> None:
        """Initialize scraping worker."""
        super().__init__(use_browser=True, **kwargs)

    async def run_task(self, task: Task) -> bool:
        """Run scraping task.

        Args:
            task: Task with scraping configuration

        Returns:
            True if successful
        """
        from src.scraping.engine import ScrapingConfig, ScrapingEngine

        if not self._browser:
            raise RuntimeError("Browser not initialized")

        # Parse task config
        config = task.config or {}
        selectors = task.selectors or {}

        scraping_config = ScrapingConfig(
            url=task.target_url,
            item_selector=config.get("item_selector", ""),
            field_map=selectors,
            max_pages=config.get("max_pages", 1),
            page_delay=config.get("page_delay", 1.0),
        )

        # Execute scraping
        engine = ScrapingEngine(browser=self._browser)
        result = engine.scrape(scraping_config)

        return result.success


class NavigationWorker(BaseWorker):
    """Worker specialized for navigation tasks."""

    def __init__(self, **kwargs) -> None:
        """Initialize navigation worker."""
        super().__init__(use_browser=True, **kwargs)

    async def run_task(self, task: Task) -> bool:
        """Run navigation task.

        Args:
            task: Task with navigation steps

        Returns:
            True if successful
        """
        from selenium.webdriver.common.by import By

        from src.automation.actions import AutomationActions

        if not self._browser:
            raise RuntimeError("Browser not initialized")

        config = task.config or {}
        steps = config.get("steps", [])

        actions = AutomationActions(self._browser.driver)

        for step in steps:
            action_type = step.get("action")
            selector = step.get("selector")
            value = step.get("value")

            if action_type == "navigate":
                self._browser.navigate(value)
                actions.wait_for_page_load()

            elif action_type == "click":
                actions.click(by=By.CSS_SELECTOR, value=selector)

            elif action_type == "fill":
                actions.fill_input(by=By.CSS_SELECTOR, value=selector, text=value)

            elif action_type == "wait":
                await asyncio.sleep(float(value))

            elif action_type == "scroll":
                actions.scroll_to_bottom()

        return True
