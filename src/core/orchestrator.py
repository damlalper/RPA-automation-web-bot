"""RPA Orchestrator - Central task management."""

import asyncio
from datetime import datetime
from typing import Any, Callable
from uuid import uuid4

from src.database.connection import get_db_context
from src.database.models import Task, TaskStatus, TaskType
from src.database.repository import TaskRepository
from src.monitoring.logger import get_logger
from src.workers.pool import WorkerPool
from src.workers.retry import RetryHandler, RetryPolicy

from .config import settings

logger = get_logger(__name__)


class TaskQueue:
    """In-memory task queue with priority support."""

    def __init__(self, max_size: int = 1000) -> None:
        """Initialize task queue.

        Args:
            max_size: Maximum queue size
        """
        self.max_size = max_size
        self._queue: asyncio.PriorityQueue[tuple[int, str, Task]] = asyncio.PriorityQueue(max_size)
        self._tasks: dict[str, Task] = {}

    async def put(self, task: Task) -> None:
        """Add task to queue.

        Args:
            task: Task to add
        """
        # Negative priority for proper ordering (higher priority first)
        priority = -task.priority
        await self._queue.put((priority, task.id, task))
        self._tasks[task.id] = task
        logger.debug(f"Task {task.id} added to queue | priority={task.priority}")

    async def get(self) -> Task:
        """Get next task from queue.

        Returns:
            Next task
        """
        _, task_id, task = await self._queue.get()
        self._tasks.pop(task_id, None)
        return task

    def get_nowait(self) -> Task | None:
        """Get next task without waiting.

        Returns:
            Next task or None
        """
        try:
            _, task_id, task = self._queue.get_nowait()
            self._tasks.pop(task_id, None)
            return task
        except asyncio.QueueEmpty:
            return None

    def task_done(self) -> None:
        """Mark current task as done."""
        self._queue.task_done()

    @property
    def size(self) -> int:
        """Get queue size.

        Returns:
            Number of tasks in queue
        """
        return self._queue.qsize()

    @property
    def is_empty(self) -> bool:
        """Check if queue is empty.

        Returns:
            True if empty
        """
        return self._queue.empty()

    def contains(self, task_id: str) -> bool:
        """Check if task is in queue.

        Args:
            task_id: Task ID

        Returns:
            True if in queue
        """
        return task_id in self._tasks


class Orchestrator:
    """Central orchestrator for RPA tasks."""

    def __init__(
        self,
        worker_pool: WorkerPool | None = None,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        """Initialize orchestrator.

        Args:
            worker_pool: Worker pool to use
            retry_policy: Retry policy for failed tasks
        """
        self.worker_pool = worker_pool
        self.retry_policy = retry_policy or RetryPolicy(
            max_retries=settings.scraping_max_retries,
            initial_delay=settings.scraping_retry_delay,
        )
        self.retry_handler = RetryHandler(self.retry_policy)

        self._queue = TaskQueue()
        self._running = False
        self._callbacks: dict[str, list[Callable[[Task], None]]] = {
            "task_started": [],
            "task_completed": [],
            "task_failed": [],
            "task_retry": [],
        }

    @property
    def is_running(self) -> bool:
        """Check if orchestrator is running.

        Returns:
            True if running
        """
        return self._running

    @property
    def queue_size(self) -> int:
        """Get current queue size.

        Returns:
            Queue size
        """
        return self._queue.size

    def on(self, event: str, callback: Callable[[Task], None]) -> None:
        """Register event callback.

        Args:
            event: Event name
            callback: Callback function
        """
        if event in self._callbacks:
            self._callbacks[event].append(callback)

    def _emit(self, event: str, task: Task) -> None:
        """Emit event to registered callbacks.

        Args:
            event: Event name
            task: Task associated with event
        """
        for callback in self._callbacks.get(event, []):
            try:
                callback(task)
            except Exception as e:
                logger.error(f"Callback error for {event}: {e}")

    async def start(self) -> None:
        """Start the orchestrator."""
        if self._running:
            logger.warning("Orchestrator already running")
            return

        logger.info("Starting orchestrator")

        if self.worker_pool is None:
            self.worker_pool = WorkerPool()

        self.worker_pool.start()
        self._running = True

        # Load pending tasks from database
        await self._load_pending_tasks()

        logger.info("Orchestrator started")

    async def stop(self) -> None:
        """Stop the orchestrator."""
        logger.info("Stopping orchestrator")

        self._running = False

        if self.worker_pool:
            self.worker_pool.stop()

        logger.info("Orchestrator stopped")

    async def _load_pending_tasks(self) -> None:
        """Load pending tasks from database into queue."""
        with get_db_context() as db:
            repo = TaskRepository(db)
            pending_tasks = repo.get_pending_tasks(limit=100)

            for task in pending_tasks:
                if not self._queue.contains(task.id):
                    await self._queue.put(task)

            logger.info(f"Loaded {len(pending_tasks)} pending tasks from database")

    def create_task(
        self,
        name: str,
        target_url: str,
        task_type: TaskType = TaskType.SCRAPE,
        config: dict[str, Any] | None = None,
        selectors: dict[str, Any] | None = None,
        priority: int = 0,
        max_retries: int = 3,
    ) -> Task:
        """Create a new task.

        Args:
            name: Task name
            target_url: URL to process
            task_type: Type of task
            config: Task configuration
            selectors: CSS selectors for scraping
            priority: Task priority
            max_retries: Maximum retry attempts

        Returns:
            Created task
        """
        with get_db_context() as db:
            repo = TaskRepository(db)
            task = repo.create(
                name=name,
                target_url=target_url,
                task_type=task_type.value,
                config=config,
                selectors=selectors,
                priority=priority,
                max_retries=max_retries,
            )
            logger.info(f"Created task {task.id}: {name}")
            return task

    async def submit_task(self, task: Task) -> str:
        """Submit task for execution.

        Args:
            task: Task to submit

        Returns:
            Task ID
        """
        await self._queue.put(task)
        logger.info(f"Task {task.id} submitted to queue")
        return task.id

    async def submit_new_task(
        self,
        name: str,
        target_url: str,
        task_type: TaskType = TaskType.SCRAPE,
        config: dict[str, Any] | None = None,
        selectors: dict[str, Any] | None = None,
        priority: int = 0,
    ) -> str:
        """Create and submit a new task.

        Args:
            name: Task name
            target_url: URL to process
            task_type: Type of task
            config: Task configuration
            selectors: CSS selectors
            priority: Task priority

        Returns:
            Task ID
        """
        task = self.create_task(
            name=name,
            target_url=target_url,
            task_type=task_type,
            config=config,
            selectors=selectors,
            priority=priority,
        )
        await self.submit_task(task)
        return task.id

    async def process_queue(self) -> None:
        """Process tasks from queue continuously."""
        logger.info("Starting queue processing")

        while self._running:
            try:
                if self._queue.is_empty:
                    await asyncio.sleep(0.5)
                    continue

                task = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                await self._execute_task(task)
                self._queue.task_done()

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Queue processing error: {e}")

    async def _execute_task(self, task: Task) -> bool:
        """Execute a single task with retry logic.

        Args:
            task: Task to execute

        Returns:
            True if successful
        """
        self._emit("task_started", task)

        # Update task status in database
        with get_db_context() as db:
            repo = TaskRepository(db)
            repo.start_task(task.id, worker_id="orchestrator")

        try:
            # Execute through worker pool
            if self.worker_pool:
                success = await self.worker_pool.execute(task)
            else:
                success = False

            if success:
                with get_db_context() as db:
                    repo = TaskRepository(db)
                    repo.complete_task(task.id, success=True)
                self._emit("task_completed", task)
            else:
                await self._handle_task_failure(task, "Execution returned false")

            return success

        except Exception as e:
            await self._handle_task_failure(task, str(e))
            return False

    async def _handle_task_failure(self, task: Task, error: str) -> None:
        """Handle task failure with retry logic.

        Args:
            task: Failed task
            error: Error message
        """
        with get_db_context() as db:
            repo = TaskRepository(db)
            current_task = repo.get(task.id)

            if current_task and current_task.retry_count < current_task.max_retries:
                # Schedule retry
                updated_task = repo.retry_task(task.id)
                if updated_task:
                    self._emit("task_retry", updated_task)
                    delay = self.retry_policy.calculate_delay(updated_task.retry_count)
                    await asyncio.sleep(delay)
                    await self._queue.put(updated_task)
                    logger.info(f"Task {task.id} scheduled for retry ({updated_task.retry_count}/{updated_task.max_retries})")
            else:
                # Max retries exceeded
                repo.complete_task(task.id, success=False, error=error)
                self._emit("task_failed", task)
                logger.error(f"Task {task.id} failed permanently: {error}")

    def get_task_status(self, task_id: str) -> dict[str, Any] | None:
        """Get task status.

        Args:
            task_id: Task ID

        Returns:
            Task status dict or None
        """
        with get_db_context() as db:
            repo = TaskRepository(db)
            task = repo.get(task_id)
            if task:
                return task.to_dict()
        return None

    def get_stats(self) -> dict[str, Any]:
        """Get orchestrator statistics.

        Returns:
            Statistics dictionary
        """
        with get_db_context() as db:
            task_repo = TaskRepository(db)
            task_stats = task_repo.get_stats()

        return {
            "running": self._running,
            "queue_size": self._queue.size,
            "task_stats": task_stats,
            "worker_pool": self.worker_pool.get_stats() if self.worker_pool else None,
        }

    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending task.

        Args:
            task_id: Task ID to cancel

        Returns:
            True if cancelled
        """
        with get_db_context() as db:
            repo = TaskRepository(db)
            task = repo.get(task_id)

            if task and task.status == TaskStatus.PENDING.value:
                repo.update(task_id, status=TaskStatus.CANCELLED.value)
                logger.info(f"Task {task_id} cancelled")
                return True

        return False

    async def __aenter__(self) -> "Orchestrator":
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.stop()
