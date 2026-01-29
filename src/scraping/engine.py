"""Main scraping engine."""

import hashlib
import random
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Generator

from selenium.webdriver.remote.webdriver import WebDriver

from src.automation.actions import AutomationActions
from src.automation.browser import BrowserManager
from src.automation.selectors import SelectorManager
from src.core.config import settings
from src.monitoring.logger import get_logger, log_scraping_event

from .pagination import PaginationHandler, PaginationType
from .parser import DOMParser

logger = get_logger(__name__)


@dataclass
class ScrapingConfig:
    """Configuration for scraping job."""

    url: str
    item_selector: str
    field_map: dict[str, str | dict[str, Any]]

    # Pagination
    pagination_type: PaginationType | None = None
    pagination_selector: str | None = None
    max_pages: int = 10

    # Delays
    page_delay: float | None = None
    request_delay_min: float | None = None
    request_delay_max: float | None = None

    # Options
    wait_for_selector: str | None = None
    scroll_to_bottom: bool = False
    javascript_render: bool = True

    # Callbacks
    pre_scrape: Callable[[WebDriver], None] | None = None
    post_scrape: Callable[[list[dict]], list[dict]] | None = None


@dataclass
class ScrapingResult:
    """Result of a scraping operation."""

    success: bool
    data: list[dict[str, Any]] = field(default_factory=list)
    pages_scraped: int = 0
    items_count: int = 0
    duration: float = 0.0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "success": self.success,
            "pages_scraped": self.pages_scraped,
            "items_count": self.items_count,
            "duration": round(self.duration, 2),
            "errors": self.errors,
        }


class ScrapingEngine:
    """Main scraping engine combining all components."""

    def __init__(
        self,
        browser: BrowserManager | None = None,
        driver: WebDriver | None = None,
    ) -> None:
        """Initialize scraping engine.

        Args:
            browser: BrowserManager instance (preferred)
            driver: Selenium WebDriver (alternative)
        """
        self._browser = browser
        self._external_driver = driver
        self._driver: WebDriver | None = None
        self._owns_browser = False

    @property
    def driver(self) -> WebDriver:
        """Get WebDriver instance.

        Returns:
            WebDriver instance

        Raises:
            RuntimeError: If not initialized
        """
        if self._driver is None:
            raise RuntimeError("Engine not started. Call start() first.")
        return self._driver

    def start(self) -> None:
        """Start the scraping engine."""
        if self._browser:
            self._driver = self._browser.start()
            self._owns_browser = False
        elif self._external_driver:
            self._driver = self._external_driver
            self._owns_browser = False
        else:
            # Create own browser
            self._browser = BrowserManager()
            self._driver = self._browser.start()
            self._owns_browser = True

        logger.info("Scraping engine started")

    def stop(self) -> None:
        """Stop the scraping engine."""
        if self._owns_browser and self._browser:
            self._browser.stop()
        self._driver = None
        logger.info("Scraping engine stopped")

    def __enter__(self) -> "ScrapingEngine":
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.stop()

    def scrape(self, config: ScrapingConfig) -> ScrapingResult:
        """Execute scraping job.

        Args:
            config: Scraping configuration

        Returns:
            ScrapingResult with scraped data
        """
        start_time = time.time()
        result = ScrapingResult(success=False)
        all_data = []

        try:
            # Navigate to URL
            logger.info(f"Starting scrape: {config.url}")
            self.driver.get(config.url)
            self._wait_for_page(config)

            # Execute pre-scrape callback
            if config.pre_scrape:
                config.pre_scrape(self.driver)

            # Scroll to bottom if needed
            if config.scroll_to_bottom:
                self._scroll_to_bottom()

            # Setup pagination
            if config.pagination_type:
                pagination = PaginationHandler(
                    driver=self.driver,
                    pagination_type=config.pagination_type,
                    max_pages=config.max_pages,
                    page_delay=config.page_delay or settings.scraping_delay_min,
                )

                # Iterate through pages
                for page_num in pagination.iterate_pages(
                    next_selector=config.pagination_selector
                ):
                    page_data = self._scrape_page(config)
                    all_data.extend(page_data)
                    result.pages_scraped = page_num
                    self._random_delay(config)

            else:
                # Single page scrape
                page_data = self._scrape_page(config)
                all_data.extend(page_data)
                result.pages_scraped = 1

            # Execute post-scrape callback
            if config.post_scrape:
                all_data = config.post_scrape(all_data)

            result.success = True
            result.data = all_data
            result.items_count = len(all_data)

        except Exception as e:
            logger.error(f"Scraping failed: {e}")
            result.errors.append(str(e))

        result.duration = time.time() - start_time

        log_scraping_event(
            url=config.url,
            items_count=result.items_count,
            duration=result.duration,
            success=result.success,
            pages=result.pages_scraped,
        )

        return result

    def _scrape_page(self, config: ScrapingConfig) -> list[dict[str, Any]]:
        """Scrape single page.

        Args:
            config: Scraping configuration

        Returns:
            List of scraped items
        """
        parser = DOMParser(self.driver.page_source)
        return parser.extract_data(config.item_selector, config.field_map)

    def _wait_for_page(self, config: ScrapingConfig) -> None:
        """Wait for page to be ready.

        Args:
            config: Scraping configuration
        """
        actions = AutomationActions(self.driver)
        actions.wait_for_page_load()

        if config.wait_for_selector:
            from selenium.webdriver.common.by import By

            actions.wait_for_element(
                By.CSS_SELECTOR,
                config.wait_for_selector,
                timeout=settings.selenium_timeout,
            )

    def _scroll_to_bottom(self) -> None:
        """Scroll page to bottom."""
        actions = AutomationActions(self.driver)
        actions.scroll_to_bottom()

    def _random_delay(self, config: ScrapingConfig) -> None:
        """Add random delay between requests.

        Args:
            config: Scraping configuration
        """
        min_delay = config.request_delay_min or settings.scraping_delay_min
        max_delay = config.request_delay_max or settings.scraping_delay_max
        delay = random.uniform(min_delay, max_delay)
        time.sleep(delay)

    def scrape_urls(
        self,
        urls: list[str],
        config_factory: Callable[[str], ScrapingConfig],
    ) -> Generator[ScrapingResult, None, None]:
        """Scrape multiple URLs.

        Args:
            urls: List of URLs to scrape
            config_factory: Function that creates config for each URL

        Yields:
            ScrapingResult for each URL
        """
        for url in urls:
            config = config_factory(url)
            result = self.scrape(config)
            yield result
            self._random_delay(config)

    def quick_scrape(
        self,
        url: str,
        item_selector: str,
        fields: dict[str, str],
    ) -> list[dict[str, Any]]:
        """Quick scrape without full configuration.

        Args:
            url: URL to scrape
            item_selector: CSS selector for items
            fields: Simple field map (field_name -> selector)

        Returns:
            List of scraped items
        """
        config = ScrapingConfig(
            url=url,
            item_selector=item_selector,
            field_map=fields,
        )
        result = self.scrape(config)
        return result.data

    @staticmethod
    def generate_hash(data: dict[str, Any], fields: list[str] | None = None) -> str:
        """Generate hash for deduplication.

        Args:
            data: Data dictionary
            fields: Fields to use for hash (all if None)

        Returns:
            SHA256 hash string
        """
        if fields:
            hash_data = {k: v for k, v in data.items() if k in fields}
        else:
            hash_data = data

        content = str(sorted(hash_data.items()))
        return hashlib.sha256(content.encode()).hexdigest()


class ScrapingSession:
    """High-level session manager for scraping operations."""

    def __init__(
        self,
        browser: BrowserManager | None = None,
        use_proxy: bool = False,
    ) -> None:
        """Initialize scraping session.

        Args:
            browser: Optional BrowserManager
            use_proxy: Whether to use proxy rotation
        """
        self.browser = browser or BrowserManager()
        self.use_proxy = use_proxy
        self.engine: ScrapingEngine | None = None
        self._proxy_rotator = None

    def __enter__(self) -> "ScrapingSession":
        """Start session."""
        if self.use_proxy:
            from src.proxy import ProxyManager, ProxyRotator

            manager = ProxyManager()
            manager.load_from_file()
            self._proxy_rotator = ProxyRotator(manager)

            # Get first proxy
            proxy = self._proxy_rotator.get_next()
            if proxy:
                self.browser.proxy = proxy.url

        self.browser.start()
        self.engine = ScrapingEngine(browser=self.browser)
        self.engine.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """End session."""
        if self.engine:
            self.engine.stop()
        self.browser.stop()

    def scrape(self, config: ScrapingConfig) -> ScrapingResult:
        """Execute scraping with session management.

        Args:
            config: Scraping configuration

        Returns:
            ScrapingResult
        """
        if not self.engine:
            raise RuntimeError("Session not started")
        return self.engine.scrape(config)

    def rotate_proxy(self) -> bool:
        """Rotate to next proxy.

        Returns:
            True if rotation successful
        """
        if not self._proxy_rotator:
            return False

        proxy = self._proxy_rotator.get_next()
        if proxy:
            self.browser.set_proxy(proxy.url)
            return True
        return False
