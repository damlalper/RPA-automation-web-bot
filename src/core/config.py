"""Centralized configuration management using Pydantic Settings."""

from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    """Application environment."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class BrowserType(str, Enum):
    """Supported browser types."""

    CHROME = "chrome"
    FIREFOX = "firefox"
    EDGE = "edge"


class ProxyRotationStrategy(str, Enum):
    """Proxy rotation strategies."""

    ROUND_ROBIN = "round_robin"
    RANDOM = "random"
    LEAST_USED = "least_used"
    FASTEST = "fastest"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = Field(default="RPAFlow", description="Application name")
    app_env: Environment = Field(default=Environment.DEVELOPMENT, description="Environment")
    debug: bool = Field(default=True, description="Debug mode")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO", description="Logging level"
    )

    # Database
    database_url: str = Field(
        default="sqlite:///./data/rpaflow.db", description="Database connection URL"
    )

    # API
    api_host: str = Field(default="0.0.0.0", description="API host")
    api_port: int = Field(default=8000, ge=1, le=65535, description="API port")
    api_workers: int = Field(default=4, ge=1, description="Number of API workers")

    # Selenium
    selenium_headless: bool = Field(default=True, description="Run browser in headless mode")
    selenium_timeout: int = Field(default=30, ge=1, description="Page load timeout in seconds")
    selenium_implicit_wait: int = Field(default=10, ge=0, description="Implicit wait in seconds")
    browser_type: BrowserType = Field(default=BrowserType.CHROME, description="Browser type")

    # Proxy
    proxy_enabled: bool = Field(default=False, description="Enable proxy rotation")
    proxy_rotation_strategy: ProxyRotationStrategy = Field(
        default=ProxyRotationStrategy.ROUND_ROBIN, description="Proxy rotation strategy"
    )
    proxy_health_check_interval: int = Field(
        default=60, ge=10, description="Health check interval in seconds"
    )
    proxy_timeout: int = Field(default=10, ge=1, description="Proxy connection timeout")
    proxy_list_file: str = Field(
        default="./config/proxies.txt", description="Path to proxy list file"
    )

    # Scraping
    scraping_delay_min: float = Field(
        default=1.0, ge=0, description="Minimum delay between requests"
    )
    scraping_delay_max: float = Field(
        default=3.0, ge=0, description="Maximum delay between requests"
    )
    scraping_max_retries: int = Field(default=3, ge=0, description="Maximum retry attempts")
    scraping_retry_delay: float = Field(default=5.0, ge=0, description="Delay between retries")

    # Worker
    worker_pool_size: int = Field(default=5, ge=1, description="Worker pool size")
    worker_max_concurrent: int = Field(default=10, ge=1, description="Max concurrent tasks")
    worker_task_timeout: int = Field(default=300, ge=1, description="Task timeout in seconds")

    # Rate Limiting
    rate_limit_requests_per_minute: int = Field(
        default=30, ge=1, description="Requests per minute limit"
    )
    rate_limit_burst: int = Field(default=10, ge=1, description="Burst limit")

    @field_validator("scraping_delay_max")
    @classmethod
    def validate_delay_max(cls, v: float, info) -> float:
        """Ensure max delay is greater than min delay."""
        min_delay = info.data.get("scraping_delay_min", 1.0)
        if v < min_delay:
            raise ValueError("scraping_delay_max must be >= scraping_delay_min")
        return v

    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.app_env == Environment.DEVELOPMENT

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.app_env == Environment.PRODUCTION

    @property
    def is_sqlite(self) -> bool:
        """Check if using SQLite database."""
        return self.database_url.startswith("sqlite")

    @property
    def data_dir(self) -> Path:
        """Get data directory path."""
        path = Path("./data")
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def config_dir(self) -> Path:
        """Get config directory path."""
        path = Path("./config")
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def logs_dir(self) -> Path:
        """Get logs directory path."""
        path = Path("./logs")
        path.mkdir(parents=True, exist_ok=True)
        return path


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()
