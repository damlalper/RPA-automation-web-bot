"""SQLAlchemy ORM models for RPAFlow."""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all models."""

    pass


class TaskStatus(str, Enum):
    """Task execution status."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    RETRY = "retry"
    CANCELLED = "cancelled"


class TaskType(str, Enum):
    """Type of automation task."""

    SCRAPE = "scrape"
    NAVIGATE = "navigate"
    FORM_FILL = "form_fill"
    LOGIN = "login"
    CUSTOM = "custom"


class Task(Base):
    """Task model representing an automation job."""

    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    task_type: Mapped[str] = mapped_column(String(50), default=TaskType.SCRAPE.value)
    status: Mapped[str] = mapped_column(String(20), default=TaskStatus.PENDING.value, index=True)

    # Target configuration
    target_url: Mapped[str] = mapped_column(Text, nullable=False)
    config: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    selectors: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # Execution details
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    priority: Mapped[int] = mapped_column(Integer, default=0, index=True)

    # Timing
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Results
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    items_scraped: Mapped[int] = mapped_column(Integer, default=0)

    # Worker assignment
    worker_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    # Relationships
    scraped_data: Mapped[list["ScrapedData"]] = relationship(
        "ScrapedData", back_populates="task", cascade="all, delete-orphan"
    )
    metrics: Mapped[list["BotMetrics"]] = relationship(
        "BotMetrics", back_populates="task", cascade="all, delete-orphan"
    )

    @property
    def duration(self) -> float | None:
        """Calculate task duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    @property
    def is_completed(self) -> bool:
        """Check if task is in a terminal state."""
        return self.status in [TaskStatus.SUCCESS.value, TaskStatus.FAILED.value, TaskStatus.CANCELLED.value]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "task_type": self.task_type,
            "status": self.status,
            "target_url": self.target_url,
            "config": self.config,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "priority": self.priority,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration": self.duration,
            "error_message": self.error_message,
            "items_scraped": self.items_scraped,
            "worker_id": self.worker_id,
        }


class ScrapedData(Base):
    """Model for storing scraped data."""

    __tablename__ = "scraped_data"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    task_id: Mapped[str] = mapped_column(String(36), ForeignKey("tasks.id"), index=True)

    # Source info
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, default=1)

    # Data
    raw_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    cleaned_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # Metadata
    data_hash: Mapped[str] = mapped_column(String(64), index=True)  # For deduplication
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False)

    # Timing
    scraped_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    task: Mapped["Task"] = relationship("Task", back_populates="scraped_data")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "task_id": self.task_id,
            "source_url": self.source_url,
            "page_number": self.page_number,
            "raw_data": self.raw_data,
            "cleaned_data": self.cleaned_data,
            "data_hash": self.data_hash,
            "is_duplicate": self.is_duplicate,
            "scraped_at": self.scraped_at.isoformat() if self.scraped_at else None,
        }


class ProxyStatus(Base):
    """Model for tracking proxy health and usage."""

    __tablename__ = "proxy_status"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))

    # Proxy info
    address: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False)
    protocol: Mapped[str] = mapped_column(String(10), default="http")
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Health status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    is_healthy: Mapped[bool] = mapped_column(Boolean, default=True)
    last_check: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_used: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Performance metrics
    response_time: Mapped[float | None] = mapped_column(Float, nullable=True)  # in seconds
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    fail_count: Mapped[int] = mapped_column(Integer, default=0)
    total_requests: Mapped[int] = mapped_column(Integer, default=0)

    # Metadata
    country: Mapped[str | None] = mapped_column(String(10), nullable=True)
    added_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    @property
    def full_address(self) -> str:
        """Get full proxy address."""
        if self.username and self.password:
            return f"{self.protocol}://{self.username}:{self.password}@{self.address}:{self.port}"
        return f"{self.protocol}://{self.address}:{self.port}"

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_requests == 0:
            return 0.0
        return (self.success_count / self.total_requests) * 100

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "address": self.address,
            "port": self.port,
            "protocol": self.protocol,
            "is_active": self.is_active,
            "is_healthy": self.is_healthy,
            "response_time": self.response_time,
            "success_rate": self.success_rate,
            "total_requests": self.total_requests,
            "last_check": self.last_check.isoformat() if self.last_check else None,
            "country": self.country,
        }


class ScrapedPage(Base):
    """Model for storing scraped pages info."""

    __tablename__ = "scraped_pages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    task_id: Mapped[str] = mapped_column(String(36), ForeignKey("tasks.id"), index=True)

    # Page info
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    page_url: Mapped[str] = mapped_column(Text, nullable=False)
    items_count: Mapped[int] = mapped_column(Integer, default=0)

    # Timing
    scraped_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Status
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    task: Mapped["Task"] = relationship("Task", backref="pages")
    books: Mapped[list["Book"]] = relationship("Book", back_populates="page", cascade="all, delete-orphan")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "task_id": self.task_id,
            "page_number": self.page_number,
            "page_url": self.page_url,
            "items_count": self.items_count,
            "scraped_at": self.scraped_at.isoformat() if self.scraped_at else None,
            "duration_seconds": self.duration_seconds,
            "success": self.success,
            "error_message": self.error_message,
        }


class Book(Base):
    """Model for storing scraped book data."""

    __tablename__ = "books"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    page_id: Mapped[str] = mapped_column(String(36), ForeignKey("scraped_pages.id"), index=True)
    task_id: Mapped[str] = mapped_column(String(36), ForeignKey("tasks.id"), index=True)

    # Book info
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    price_currency: Mapped[str] = mapped_column(String(10), default="GBP")
    rating: Mapped[int] = mapped_column(Integer, default=0)  # 1-5 stars
    availability: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # URLs
    book_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Metadata
    data_hash: Mapped[str] = mapped_column(String(64), index=True)
    scraped_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    page: Mapped["ScrapedPage"] = relationship("ScrapedPage", back_populates="books")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "page_id": self.page_id,
            "task_id": self.task_id,
            "title": self.title,
            "price": self.price,
            "price_currency": self.price_currency,
            "rating": self.rating,
            "availability": self.availability,
            "book_url": self.book_url,
            "image_url": self.image_url,
            "data_hash": self.data_hash,
            "scraped_at": self.scraped_at.isoformat() if self.scraped_at else None,
        }


class BotMetrics(Base):
    """Model for storing bot performance metrics."""

    __tablename__ = "bot_metrics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    task_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("tasks.id"), nullable=True)
    worker_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)

    # Metric type
    metric_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    # Performance data
    duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    error_type: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Resource usage
    memory_usage: Mapped[float | None] = mapped_column(Float, nullable=True)  # MB
    cpu_usage: Mapped[float | None] = mapped_column(Float, nullable=True)  # percentage

    # Additional data
    extra_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # Timing
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    task: Mapped["Task | None"] = relationship("Task", back_populates="metrics")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "task_id": self.task_id,
            "worker_id": self.worker_id,
            "metric_type": self.metric_type,
            "duration": self.duration,
            "success": self.success,
            "error_type": self.error_type,
            "memory_usage": self.memory_usage,
            "cpu_usage": self.cpu_usage,
            "extra_data": self.extra_data,
            "recorded_at": self.recorded_at.isoformat() if self.recorded_at else None,
        }
