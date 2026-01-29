"""Task management endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.database.connection import get_db
from src.database.models import TaskStatus, TaskType
from src.database.repository import ScrapedDataRepository, TaskRepository

router = APIRouter()


# Request/Response Models
class TaskCreate(BaseModel):
    """Task creation request model."""

    name: str = Field(..., min_length=1, max_length=255)
    target_url: str = Field(..., min_length=1)
    task_type: str = Field(default="scrape")
    config: dict[str, Any] | None = None
    selectors: dict[str, Any] | None = None
    priority: int = Field(default=0, ge=0, le=100)
    max_retries: int = Field(default=3, ge=0, le=10)


class TaskUpdate(BaseModel):
    """Task update request model."""

    name: str | None = None
    config: dict[str, Any] | None = None
    selectors: dict[str, Any] | None = None
    priority: int | None = None


class TaskResponse(BaseModel):
    """Task response model."""

    id: str
    name: str
    task_type: str
    status: str
    target_url: str
    config: dict[str, Any] | None
    retry_count: int
    max_retries: int
    priority: int
    created_at: str | None
    started_at: str | None
    completed_at: str | None
    duration: float | None
    error_message: str | None
    items_scraped: int
    worker_id: str | None

    class Config:
        from_attributes = True


class TaskListResponse(BaseModel):
    """Task list response model."""

    tasks: list[TaskResponse]
    total: int
    page: int
    page_size: int


class TaskStatsResponse(BaseModel):
    """Task statistics response model."""

    total: int
    by_status: dict[str, int]
    success_rate: float
    avg_duration: float | None


# Endpoints
@router.post("", response_model=TaskResponse, status_code=201)
async def create_task(task: TaskCreate, db: Session = Depends(get_db)) -> TaskResponse:
    """Create a new task.

    Args:
        task: Task creation data
        db: Database session

    Returns:
        Created task
    """
    repo = TaskRepository(db)
    created = repo.create(
        name=task.name,
        target_url=task.target_url,
        task_type=task.task_type,
        config=task.config,
        selectors=task.selectors,
        priority=task.priority,
        max_retries=task.max_retries,
    )
    return TaskResponse(**created.to_dict())


@router.get("", response_model=TaskListResponse)
async def list_tasks(
    status: str | None = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> TaskListResponse:
    """List all tasks with optional filtering.

    Args:
        status: Filter by task status
        page: Page number
        page_size: Items per page
        db: Database session

    Returns:
        Paginated task list
    """
    repo = TaskRepository(db)
    offset = (page - 1) * page_size

    if status:
        try:
            task_status = TaskStatus(status)
            tasks = repo.get_by_status(task_status, limit=page_size)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    else:
        tasks = repo.get_all(limit=page_size, offset=offset)

    total = repo.count()

    return TaskListResponse(
        tasks=[TaskResponse(**t.to_dict()) for t in tasks],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/stats", response_model=TaskStatsResponse)
async def get_task_stats(db: Session = Depends(get_db)) -> TaskStatsResponse:
    """Get task statistics.

    Args:
        db: Database session

    Returns:
        Task statistics
    """
    repo = TaskRepository(db)
    stats = repo.get_stats()
    return TaskStatsResponse(**stats)


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str, db: Session = Depends(get_db)) -> TaskResponse:
    """Get task by ID.

    Args:
        task_id: Task ID
        db: Database session

    Returns:
        Task details
    """
    repo = TaskRepository(db)
    task = repo.get(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return TaskResponse(**task.to_dict())


@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: str,
    update: TaskUpdate,
    db: Session = Depends(get_db),
) -> TaskResponse:
    """Update task.

    Args:
        task_id: Task ID
        update: Update data
        db: Database session

    Returns:
        Updated task
    """
    repo = TaskRepository(db)
    task = repo.get(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status not in [TaskStatus.PENDING.value]:
        raise HTTPException(status_code=400, detail="Can only update pending tasks")

    update_data = update.model_dump(exclude_unset=True)
    updated = repo.update(task_id, **update_data)

    return TaskResponse(**updated.to_dict())


@router.delete("/{task_id}", status_code=204)
async def delete_task(task_id: str, db: Session = Depends(get_db)) -> None:
    """Delete task.

    Args:
        task_id: Task ID
        db: Database session
    """
    repo = TaskRepository(db)
    task = repo.get(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status == TaskStatus.RUNNING.value:
        raise HTTPException(status_code=400, detail="Cannot delete running task")

    repo.delete(task_id)


@router.post("/{task_id}/cancel", response_model=TaskResponse)
async def cancel_task(task_id: str, db: Session = Depends(get_db)) -> TaskResponse:
    """Cancel a pending task.

    Args:
        task_id: Task ID
        db: Database session

    Returns:
        Cancelled task
    """
    repo = TaskRepository(db)
    task = repo.get(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status != TaskStatus.PENDING.value:
        raise HTTPException(status_code=400, detail="Can only cancel pending tasks")

    updated = repo.update(task_id, status=TaskStatus.CANCELLED.value)
    return TaskResponse(**updated.to_dict())


@router.post("/{task_id}/retry", response_model=TaskResponse)
async def retry_task(task_id: str, db: Session = Depends(get_db)) -> TaskResponse:
    """Retry a failed task.

    Args:
        task_id: Task ID
        db: Database session

    Returns:
        Task scheduled for retry
    """
    repo = TaskRepository(db)
    task = repo.get(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status != TaskStatus.FAILED.value:
        raise HTTPException(status_code=400, detail="Can only retry failed tasks")

    updated = repo.retry_task(task_id)
    if not updated:
        raise HTTPException(status_code=400, detail="Max retries exceeded")

    return TaskResponse(**updated.to_dict())


@router.get("/{task_id}/data")
async def get_task_data(
    task_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Get scraped data for a task.

    Args:
        task_id: Task ID
        page: Page number
        page_size: Items per page
        db: Database session

    Returns:
        Scraped data
    """
    task_repo = TaskRepository(db)
    task = task_repo.get(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    data_repo = ScrapedDataRepository(db)
    all_data = data_repo.get_by_task(task_id)

    # Paginate
    start = (page - 1) * page_size
    end = start + page_size
    paginated = all_data[start:end]

    return {
        "task_id": task_id,
        "total": len(all_data),
        "page": page,
        "page_size": page_size,
        "data": [d.to_dict() for d in paginated],
    }
