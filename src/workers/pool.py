"""Worker pool management."""

import asyncio
from typing import Any, Type
from uuid import uuid4

from src.core.config import settings
from src.database.models import Task, TaskStatus
from src.monitoring.logger import get_logger

from .base import BaseWorker, ScrapingWorker, WorkerState

logger = get_logger(__name__)


class WorkerPool:
    """Pool of workers for parallel task execution."""

    def __init__(
        self,
        pool_size: int | None = None,
        worker_class: Type[BaseWorker] = ScrapingWorker,
        max_concurrent: int | None = None,
        **worker_kwargs,
    ) -> None:
        """Initialize worker pool.

        Args:
            pool_size: Number of workers
            worker_class: Worker class to instantiate
            max_concurrent: Max concurrent tasks
            **worker_kwargs: Arguments for worker initialization
        """
        self.pool_size = pool_size or settings.worker_pool_size
        self.worker_class = worker_class
        self.max_concurrent = max_concurrent or settings.worker_max_concurrent
        self.worker_kwargs = worker_kwargs

        self._workers: list[BaseWorker] = []
        self._task_queue: asyncio.Queue[Task] = asyncio.Queue()
        self._results: dict[str, Any] = {}
        self._running = False
        self._semaphore: asyncio.Semaphore | None = None

    @property
    def workers(self) -> list[BaseWorker]:
        """Get all workers.

        Returns:
            List of workers
        """
        return self._workers

    @property
    def available_workers(self) -> list[BaseWorker]:
        """Get available workers.

        Returns:
            List of available workers
        """
        return [w for w in self._workers if w.is_available]

    @property
    def is_running(self) -> bool:
        """Check if pool is running.

        Returns:
            True if running
        """
        return self._running

    def start(self) -> None:
        """Start the worker pool."""
        if self._running:
            logger.warning("Worker pool already running")
            return

        logger.info(f"Starting worker pool | size={self.pool_size}")

        for i in range(self.pool_size):
            worker_id = f"worker-{i + 1}"
            worker = self.worker_class(worker_id=worker_id, **self.worker_kwargs)
            worker.start()
            self._workers.append(worker)

        self._semaphore = asyncio.Semaphore(self.max_concurrent)
        self._running = True

        logger.info(f"Worker pool started | workers={len(self._workers)}")

    def stop(self) -> None:
        """Stop the worker pool."""
        logger.info("Stopping worker pool")

        self._running = False

        for worker in self._workers:
            worker.stop()

        self._workers.clear()
        self._results.clear()

        logger.info("Worker pool stopped")

    def add_worker(self) -> BaseWorker:
        """Add a new worker to the pool.

        Returns:
            New worker
        """
        worker_id = f"worker-{len(self._workers) + 1}"
        worker = self.worker_class(worker_id=worker_id, **self.worker_kwargs)
        worker.start()
        self._workers.append(worker)
        logger.info(f"Added worker {worker_id}")
        return worker

    def remove_worker(self, worker_id: str) -> bool:
        """Remove a worker from the pool.

        Args:
            worker_id: Worker ID to remove

        Returns:
            True if removed
        """
        for worker in self._workers:
            if worker.worker_id == worker_id:
                if worker.state == WorkerState.RUNNING:
                    logger.warning(f"Cannot remove running worker {worker_id}")
                    return False
                worker.stop()
                self._workers.remove(worker)
                logger.info(f"Removed worker {worker_id}")
                return True
        return False

    def get_worker(self) -> BaseWorker | None:
        """Get an available worker.

        Returns:
            Available worker or None
        """
        for worker in self._workers:
            if worker.is_available:
                return worker
        return None

    async def submit(self, task: Task) -> str:
        """Submit task to the pool.

        Args:
            task: Task to submit

        Returns:
            Task ID
        """
        await self._task_queue.put(task)
        logger.debug(f"Task {task.id} submitted to queue")
        return task.id

    async def execute(self, task: Task) -> bool:
        """Execute a single task immediately.

        Args:
            task: Task to execute

        Returns:
            True if successful
        """
        if not self._running:
            raise RuntimeError("Worker pool not running")

        async with self._semaphore:
            worker = self.get_worker()
            if not worker:
                logger.warning("No available workers")
                return False

            result = await worker.execute(task)
            self._results[task.id] = result
            return result

    async def execute_batch(self, tasks: list[Task]) -> dict[str, bool]:
        """Execute multiple tasks in parallel.

        Args:
            tasks: List of tasks

        Returns:
            Dictionary of task_id -> success
        """
        if not self._running:
            raise RuntimeError("Worker pool not running")

        async def run_task(task: Task) -> tuple[str, bool]:
            async with self._semaphore:
                worker = None
                while worker is None:
                    worker = self.get_worker()
                    if worker is None:
                        await asyncio.sleep(0.1)

                result = await worker.execute(task)
                return task.id, result

        results = await asyncio.gather(*[run_task(t) for t in tasks])
        return dict(results)

    async def run_queue(self) -> None:
        """Process tasks from queue continuously."""
        if not self._running:
            raise RuntimeError("Worker pool not running")

        logger.info("Starting queue processing")

        while self._running:
            try:
                task = await asyncio.wait_for(self._task_queue.get(), timeout=1.0)
                await self.execute(task)
                self._task_queue.task_done()
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Queue processing error: {e}")

    def get_result(self, task_id: str) -> Any | None:
        """Get result for a task.

        Args:
            task_id: Task ID

        Returns:
            Task result or None
        """
        return self._results.get(task_id)

    def get_stats(self) -> dict[str, Any]:
        """Get pool statistics.

        Returns:
            Statistics dictionary
        """
        total_completed = sum(w.stats.tasks_completed for w in self._workers)
        total_failed = sum(w.stats.tasks_failed for w in self._workers)
        total_duration = sum(w.stats.total_duration for w in self._workers)

        return {
            "pool_size": len(self._workers),
            "available_workers": len(self.available_workers),
            "running": self._running,
            "queue_size": self._task_queue.qsize(),
            "total_tasks_completed": total_completed,
            "total_tasks_failed": total_failed,
            "overall_success_rate": (
                (total_completed / (total_completed + total_failed) * 100)
                if (total_completed + total_failed) > 0
                else 0
            ),
            "total_duration": round(total_duration, 2),
            "workers": [
                {
                    "id": w.worker_id,
                    "state": w.state.value,
                    "stats": w.stats.to_dict(),
                }
                for w in self._workers
            ],
        }

    def __enter__(self) -> "WorkerPool":
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.stop()


class DynamicWorkerPool(WorkerPool):
    """Worker pool with dynamic scaling."""

    def __init__(
        self,
        min_workers: int = 1,
        max_workers: int = 10,
        scale_up_threshold: float = 0.8,
        scale_down_threshold: float = 0.3,
        **kwargs,
    ) -> None:
        """Initialize dynamic worker pool.

        Args:
            min_workers: Minimum number of workers
            max_workers: Maximum number of workers
            scale_up_threshold: Queue utilization to trigger scale up
            scale_down_threshold: Worker idle ratio to trigger scale down
            **kwargs: Arguments for WorkerPool
        """
        super().__init__(pool_size=min_workers, **kwargs)
        self.min_workers = min_workers
        self.max_workers = max_workers
        self.scale_up_threshold = scale_up_threshold
        self.scale_down_threshold = scale_down_threshold

    async def auto_scale(self) -> None:
        """Automatically adjust pool size based on load."""
        while self._running:
            try:
                await self._check_and_scale()
                await asyncio.sleep(10)  # Check every 10 seconds
            except Exception as e:
                logger.error(f"Auto-scale error: {e}")

    async def _check_and_scale(self) -> None:
        """Check load and scale if needed."""
        queue_size = self._task_queue.qsize()
        available = len(self.available_workers)
        total = len(self._workers)

        # Scale up if queue is large and we have capacity
        if queue_size > total * self.scale_up_threshold and total < self.max_workers:
            self.add_worker()
            logger.info(f"Scaled up | workers={len(self._workers)}")

        # Scale down if many workers idle
        elif available > total * self.scale_down_threshold and total > self.min_workers:
            for worker in self._workers:
                if worker.is_available and len(self._workers) > self.min_workers:
                    self.remove_worker(worker.worker_id)
                    logger.info(f"Scaled down | workers={len(self._workers)}")
                    break
