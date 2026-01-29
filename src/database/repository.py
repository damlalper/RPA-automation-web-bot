"""Repository pattern for database operations."""

from datetime import datetime
from typing import Any, Generic, TypeVar
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Base, Book, BotMetrics, ProxyStatus, ScrapedData, ScrapedPage, Task, TaskStatus

T = TypeVar("T", bound=Base)


class BaseRepository(Generic[T]):
    """Base repository with common CRUD operations."""

    def __init__(self, db: Session, model: type[T]) -> None:
        """Initialize repository.

        Args:
            db: Database session
            model: SQLAlchemy model class
        """
        self.db = db
        self.model = model

    def get(self, id: str) -> T | None:
        """Get record by ID.

        Args:
            id: Record ID

        Returns:
            Record or None if not found
        """
        return self.db.get(self.model, id)

    def get_all(self, limit: int = 100, offset: int = 0) -> list[T]:
        """Get all records with pagination.

        Args:
            limit: Maximum number of records
            offset: Number of records to skip

        Returns:
            List of records
        """
        stmt = select(self.model).limit(limit).offset(offset)
        return list(self.db.scalars(stmt).all())

    def create(self, **kwargs: Any) -> T:
        """Create a new record.

        Args:
            **kwargs: Field values

        Returns:
            Created record
        """
        if "id" not in kwargs:
            kwargs["id"] = str(uuid4())
        instance = self.model(**kwargs)
        self.db.add(instance)
        self.db.commit()
        self.db.refresh(instance)
        return instance

    def update(self, id: str, **kwargs: Any) -> T | None:
        """Update a record.

        Args:
            id: Record ID
            **kwargs: Field values to update

        Returns:
            Updated record or None if not found
        """
        instance = self.get(id)
        if instance:
            for key, value in kwargs.items():
                if hasattr(instance, key):
                    setattr(instance, key, value)
            self.db.commit()
            self.db.refresh(instance)
        return instance

    def delete(self, id: str) -> bool:
        """Delete a record.

        Args:
            id: Record ID

        Returns:
            True if deleted, False if not found
        """
        instance = self.get(id)
        if instance:
            self.db.delete(instance)
            self.db.commit()
            return True
        return False

    def count(self) -> int:
        """Count total records.

        Returns:
            Total count
        """
        stmt = select(func.count()).select_from(self.model)
        return self.db.scalar(stmt) or 0


class TaskRepository(BaseRepository[Task]):
    """Repository for Task operations."""

    def __init__(self, db: Session) -> None:
        super().__init__(db, Task)

    def get_by_status(self, status: TaskStatus, limit: int = 100) -> list[Task]:
        """Get tasks by status.

        Args:
            status: Task status
            limit: Maximum number of tasks

        Returns:
            List of tasks
        """
        stmt = (
            select(Task)
            .where(Task.status == status.value)
            .order_by(Task.priority.desc(), Task.created_at)
            .limit(limit)
        )
        return list(self.db.scalars(stmt).all())

    def get_pending_tasks(self, limit: int = 10) -> list[Task]:
        """Get pending tasks ordered by priority.

        Args:
            limit: Maximum number of tasks

        Returns:
            List of pending tasks
        """
        stmt = (
            select(Task)
            .where(Task.status == TaskStatus.PENDING.value)
            .order_by(Task.priority.desc(), Task.created_at)
            .limit(limit)
        )
        return list(self.db.scalars(stmt).all())

    def get_running_tasks(self) -> list[Task]:
        """Get all running tasks.

        Returns:
            List of running tasks
        """
        stmt = select(Task).where(Task.status == TaskStatus.RUNNING.value)
        return list(self.db.scalars(stmt).all())

    def start_task(self, task_id: str, worker_id: str) -> Task | None:
        """Mark task as started.

        Args:
            task_id: Task ID
            worker_id: Worker ID

        Returns:
            Updated task or None
        """
        return self.update(
            task_id,
            status=TaskStatus.RUNNING.value,
            started_at=datetime.utcnow(),
            worker_id=worker_id,
        )

    def complete_task(
        self, task_id: str, success: bool = True, items_scraped: int = 0, error: str | None = None
    ) -> Task | None:
        """Mark task as completed.

        Args:
            task_id: Task ID
            success: Whether task succeeded
            items_scraped: Number of items scraped
            error: Error message if failed

        Returns:
            Updated task or None
        """
        status = TaskStatus.SUCCESS.value if success else TaskStatus.FAILED.value
        return self.update(
            task_id,
            status=status,
            completed_at=datetime.utcnow(),
            items_scraped=items_scraped,
            error_message=error,
        )

    def retry_task(self, task_id: str) -> Task | None:
        """Mark task for retry.

        Args:
            task_id: Task ID

        Returns:
            Updated task or None
        """
        task = self.get(task_id)
        if task and task.retry_count < task.max_retries:
            return self.update(
                task_id,
                status=TaskStatus.RETRY.value,
                retry_count=task.retry_count + 1,
                started_at=None,
                completed_at=None,
                worker_id=None,
            )
        return None

    def get_stats(self) -> dict[str, Any]:
        """Get task statistics.

        Returns:
            Dictionary with task stats
        """
        total = self.count()

        # Count by status
        status_counts = {}
        for status in TaskStatus:
            stmt = select(func.count()).select_from(Task).where(Task.status == status.value)
            status_counts[status.value] = self.db.scalar(stmt) or 0

        # Average duration for completed tasks
        stmt = select(func.avg(Task.completed_at - Task.started_at)).where(
            Task.status == TaskStatus.SUCCESS.value,
            Task.started_at.isnot(None),
            Task.completed_at.isnot(None),
        )
        avg_duration = self.db.scalar(stmt)

        # Success rate
        completed = status_counts.get(TaskStatus.SUCCESS.value, 0)
        failed = status_counts.get(TaskStatus.FAILED.value, 0)
        total_finished = completed + failed
        success_rate = (completed / total_finished * 100) if total_finished > 0 else 0

        return {
            "total": total,
            "by_status": status_counts,
            "success_rate": round(success_rate, 2),
            "avg_duration": avg_duration,
        }


class ScrapedDataRepository(BaseRepository[ScrapedData]):
    """Repository for ScrapedData operations."""

    def __init__(self, db: Session) -> None:
        super().__init__(db, ScrapedData)

    def get_by_task(self, task_id: str) -> list[ScrapedData]:
        """Get all scraped data for a task.

        Args:
            task_id: Task ID

        Returns:
            List of scraped data
        """
        stmt = (
            select(ScrapedData)
            .where(ScrapedData.task_id == task_id)
            .order_by(ScrapedData.page_number, ScrapedData.scraped_at)
        )
        return list(self.db.scalars(stmt).all())

    def check_duplicate(self, data_hash: str) -> bool:
        """Check if data with hash already exists.

        Args:
            data_hash: Data hash

        Returns:
            True if duplicate exists
        """
        stmt = select(ScrapedData).where(ScrapedData.data_hash == data_hash).limit(1)
        return self.db.scalar(stmt) is not None

    def bulk_insert(self, items: list[dict[str, Any]]) -> int:
        """Bulk insert scraped data.

        Args:
            items: List of item dictionaries

        Returns:
            Number of items inserted
        """
        instances = []
        for item in items:
            if "id" not in item:
                item["id"] = str(uuid4())
            instances.append(ScrapedData(**item))

        self.db.bulk_save_objects(instances)
        self.db.commit()
        return len(instances)

    def get_non_duplicates(self, task_id: str) -> list[ScrapedData]:
        """Get non-duplicate scraped data for a task.

        Args:
            task_id: Task ID

        Returns:
            List of non-duplicate scraped data
        """
        stmt = (
            select(ScrapedData)
            .where(ScrapedData.task_id == task_id, ScrapedData.is_duplicate == False)
            .order_by(ScrapedData.scraped_at)
        )
        return list(self.db.scalars(stmt).all())


class ProxyStatusRepository(BaseRepository[ProxyStatus]):
    """Repository for ProxyStatus operations."""

    def __init__(self, db: Session) -> None:
        super().__init__(db, ProxyStatus)

    def get_active_proxies(self) -> list[ProxyStatus]:
        """Get all active and healthy proxies.

        Returns:
            List of active proxies
        """
        stmt = (
            select(ProxyStatus)
            .where(ProxyStatus.is_active == True, ProxyStatus.is_healthy == True)
            .order_by(ProxyStatus.response_time)
        )
        return list(self.db.scalars(stmt).all())

    def get_by_address(self, address: str) -> ProxyStatus | None:
        """Get proxy by address.

        Args:
            address: Proxy address

        Returns:
            Proxy status or None
        """
        stmt = select(ProxyStatus).where(ProxyStatus.address == address).limit(1)
        return self.db.scalar(stmt)

    def update_health(
        self, proxy_id: str, is_healthy: bool, response_time: float | None = None
    ) -> ProxyStatus | None:
        """Update proxy health status.

        Args:
            proxy_id: Proxy ID
            is_healthy: Health status
            response_time: Response time in seconds

        Returns:
            Updated proxy or None
        """
        return self.update(
            proxy_id,
            is_healthy=is_healthy,
            response_time=response_time,
            last_check=datetime.utcnow(),
        )

    def record_usage(self, proxy_id: str, success: bool) -> ProxyStatus | None:
        """Record proxy usage.

        Args:
            proxy_id: Proxy ID
            success: Whether request succeeded

        Returns:
            Updated proxy or None
        """
        proxy = self.get(proxy_id)
        if proxy:
            updates = {
                "total_requests": proxy.total_requests + 1,
                "last_used": datetime.utcnow(),
            }
            if success:
                updates["success_count"] = proxy.success_count + 1
            else:
                updates["fail_count"] = proxy.fail_count + 1
            return self.update(proxy_id, **updates)
        return None

    def get_least_used(self) -> ProxyStatus | None:
        """Get the least used active proxy.

        Returns:
            Least used proxy or None
        """
        stmt = (
            select(ProxyStatus)
            .where(ProxyStatus.is_active == True, ProxyStatus.is_healthy == True)
            .order_by(ProxyStatus.total_requests, ProxyStatus.last_used)
            .limit(1)
        )
        return self.db.scalar(stmt)

    def get_fastest(self) -> ProxyStatus | None:
        """Get the fastest active proxy.

        Returns:
            Fastest proxy or None
        """
        stmt = (
            select(ProxyStatus)
            .where(
                ProxyStatus.is_active == True,
                ProxyStatus.is_healthy == True,
                ProxyStatus.response_time.isnot(None),
            )
            .order_by(ProxyStatus.response_time)
            .limit(1)
        )
        return self.db.scalar(stmt)


class ScrapedPageRepository(BaseRepository[ScrapedPage]):
    """Repository for ScrapedPage operations."""

    def __init__(self, db: Session) -> None:
        super().__init__(db, ScrapedPage)

    def get_by_task(self, task_id: str) -> list[ScrapedPage]:
        """Get all pages for a task."""
        stmt = (
            select(ScrapedPage)
            .where(ScrapedPage.task_id == task_id)
            .order_by(ScrapedPage.page_number)
        )
        return list(self.db.scalars(stmt).all())

    def get_by_page_number(self, task_id: str, page_number: int) -> ScrapedPage | None:
        """Get page by task and page number."""
        stmt = (
            select(ScrapedPage)
            .where(ScrapedPage.task_id == task_id, ScrapedPage.page_number == page_number)
            .limit(1)
        )
        return self.db.scalar(stmt)


class BookRepository(BaseRepository[Book]):
    """Repository for Book operations."""

    def __init__(self, db: Session) -> None:
        super().__init__(db, Book)

    def get_by_task(self, task_id: str) -> list[Book]:
        """Get all books for a task."""
        stmt = (
            select(Book)
            .where(Book.task_id == task_id)
            .order_by(Book.scraped_at)
        )
        return list(self.db.scalars(stmt).all())

    def get_by_page(self, page_id: str) -> list[Book]:
        """Get all books for a page."""
        stmt = (
            select(Book)
            .where(Book.page_id == page_id)
            .order_by(Book.title)
        )
        return list(self.db.scalars(stmt).all())

    def bulk_insert(self, books: list[dict[str, Any]]) -> int:
        """Bulk insert books."""
        instances = []
        for book in books:
            if "id" not in book:
                book["id"] = str(uuid4())
            instances.append(Book(**book))
        self.db.bulk_save_objects(instances)
        self.db.commit()
        return len(instances)

    def get_by_rating(self, min_rating: int = 1) -> list[Book]:
        """Get books with minimum rating."""
        stmt = (
            select(Book)
            .where(Book.rating >= min_rating)
            .order_by(Book.rating.desc(), Book.title)
        )
        return list(self.db.scalars(stmt).all())

    def get_price_range(self, min_price: float, max_price: float) -> list[Book]:
        """Get books within price range."""
        stmt = (
            select(Book)
            .where(Book.price >= min_price, Book.price <= max_price)
            .order_by(Book.price)
        )
        return list(self.db.scalars(stmt).all())

    def get_stats(self) -> dict[str, Any]:
        """Get book statistics."""
        total = self.count()
        avg_price = self.db.scalar(select(func.avg(Book.price)))
        avg_rating = self.db.scalar(select(func.avg(Book.rating)))
        min_price = self.db.scalar(select(func.min(Book.price)))
        max_price = self.db.scalar(select(func.max(Book.price)))

        return {
            "total_books": total,
            "avg_price": round(avg_price, 2) if avg_price else 0,
            "avg_rating": round(avg_rating, 1) if avg_rating else 0,
            "min_price": min_price,
            "max_price": max_price,
        }


class BotMetricsRepository(BaseRepository[BotMetrics]):
    """Repository for BotMetrics operations."""

    def __init__(self, db: Session) -> None:
        super().__init__(db, BotMetrics)

    def record_metric(
        self,
        metric_type: str,
        task_id: str | None = None,
        worker_id: str | None = None,
        duration: float | None = None,
        success: bool = True,
        error_type: str | None = None,
        extra_data: dict[str, Any] | None = None,
    ) -> BotMetrics:
        """Record a new metric.

        Args:
            metric_type: Type of metric
            task_id: Associated task ID
            worker_id: Worker ID
            duration: Duration in seconds
            success: Whether operation succeeded
            error_type: Error type if failed
            extra_data: Additional data

        Returns:
            Created metric
        """
        return self.create(
            metric_type=metric_type,
            task_id=task_id,
            worker_id=worker_id,
            duration=duration,
            success=success,
            error_type=error_type,
            extra_data=extra_data,
        )

    def get_by_type(
        self,
        metric_type: str,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[BotMetrics]:
        """Get metrics by type.

        Args:
            metric_type: Type of metric
            since: Filter from this datetime
            limit: Maximum number of records

        Returns:
            List of metrics
        """
        stmt = select(BotMetrics).where(BotMetrics.metric_type == metric_type)
        if since:
            stmt = stmt.where(BotMetrics.recorded_at >= since)
        stmt = stmt.order_by(BotMetrics.recorded_at.desc()).limit(limit)
        return list(self.db.scalars(stmt).all())

    def get_aggregated_stats(
        self, metric_type: str, since: datetime | None = None
    ) -> dict[str, Any]:
        """Get aggregated statistics for a metric type.

        Args:
            metric_type: Type of metric
            since: Filter from this datetime

        Returns:
            Dictionary with aggregated stats
        """
        base_stmt = select(BotMetrics).where(BotMetrics.metric_type == metric_type)
        if since:
            base_stmt = base_stmt.where(BotMetrics.recorded_at >= since)

        # Total count
        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total = self.db.scalar(count_stmt) or 0

        # Success count
        success_stmt = select(func.count()).select_from(
            base_stmt.where(BotMetrics.success == True).subquery()
        )
        success_count = self.db.scalar(success_stmt) or 0

        # Average duration
        avg_stmt = select(func.avg(BotMetrics.duration)).where(
            BotMetrics.metric_type == metric_type, BotMetrics.duration.isnot(None)
        )
        if since:
            avg_stmt = avg_stmt.where(BotMetrics.recorded_at >= since)
        avg_duration = self.db.scalar(avg_stmt)

        return {
            "total": total,
            "success_count": success_count,
            "fail_count": total - success_count,
            "success_rate": (success_count / total * 100) if total > 0 else 0,
            "avg_duration": round(avg_duration, 3) if avg_duration else None,
        }
