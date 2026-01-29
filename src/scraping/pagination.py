"""Pagination handling for web scraping."""

import re
import time
from enum import Enum
from typing import Any, Callable, Generator
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver

from src.automation.actions import AutomationActions
from src.monitoring.logger import get_logger

logger = get_logger(__name__)


class PaginationType(str, Enum):
    """Types of pagination."""

    NEXT_BUTTON = "next_button"  # Click next button
    PAGE_NUMBERS = "page_numbers"  # Click page numbers
    INFINITE_SCROLL = "infinite_scroll"  # Scroll to load more
    LOAD_MORE = "load_more"  # Click "load more" button
    URL_PARAM = "url_param"  # Modify URL parameter


class PaginationHandler:
    """Handles different types of pagination."""

    def __init__(
        self,
        driver: WebDriver,
        pagination_type: PaginationType = PaginationType.NEXT_BUTTON,
        max_pages: int = 10,
        page_delay: float = 1.0,
    ) -> None:
        """Initialize pagination handler.

        Args:
            driver: Selenium WebDriver
            pagination_type: Type of pagination
            max_pages: Maximum pages to scrape
            page_delay: Delay between pages in seconds
        """
        self.driver = driver
        self.actions = AutomationActions(driver)
        self.pagination_type = pagination_type
        self.max_pages = max_pages
        self.page_delay = page_delay
        self._current_page = 1

    @property
    def current_page(self) -> int:
        """Get current page number.

        Returns:
            Current page number
        """
        return self._current_page

    def reset(self) -> None:
        """Reset pagination state."""
        self._current_page = 1

    def iterate_pages(
        self,
        next_selector: str | None = None,
        page_callback: Callable[[int], Any] | None = None,
        stop_condition: Callable[[], bool] | None = None,
        **kwargs,
    ) -> Generator[int, None, None]:
        """Iterate through pages.

        Args:
            next_selector: CSS selector for next button (for NEXT_BUTTON type)
            page_callback: Optional callback for each page
            stop_condition: Optional function to stop pagination
            **kwargs: Additional arguments for specific pagination types

        Yields:
            Page number
        """
        self.reset()

        while self._current_page <= self.max_pages:
            logger.debug(f"Processing page {self._current_page}")

            # Yield current page
            yield self._current_page

            # Execute callback if provided
            if page_callback:
                page_callback(self._current_page)

            # Check stop condition
            if stop_condition and stop_condition():
                logger.info(f"Stop condition met at page {self._current_page}")
                break

            # Navigate to next page
            has_next = self._navigate_next(next_selector, **kwargs)
            if not has_next:
                logger.info(f"No more pages after page {self._current_page}")
                break

            self._current_page += 1
            time.sleep(self.page_delay)

    def _navigate_next(self, next_selector: str | None = None, **kwargs) -> bool:
        """Navigate to next page based on pagination type.

        Args:
            next_selector: CSS selector for next button
            **kwargs: Additional arguments

        Returns:
            True if navigation successful
        """
        if self.pagination_type == PaginationType.NEXT_BUTTON:
            return self._navigate_next_button(next_selector)
        elif self.pagination_type == PaginationType.PAGE_NUMBERS:
            return self._navigate_page_number(kwargs.get("page_selector"))
        elif self.pagination_type == PaginationType.INFINITE_SCROLL:
            return self._navigate_infinite_scroll(kwargs.get("scroll_pause", 2.0))
        elif self.pagination_type == PaginationType.LOAD_MORE:
            return self._navigate_load_more(kwargs.get("load_more_selector"))
        elif self.pagination_type == PaginationType.URL_PARAM:
            return self._navigate_url_param(
                kwargs.get("param_name", "page"),
                kwargs.get("base_url"),
            )
        return False

    def _navigate_next_button(self, selector: str | None) -> bool:
        """Navigate using next button click.

        Args:
            selector: CSS selector for next button

        Returns:
            True if navigation successful
        """
        if not selector:
            selector = "a.next, .pagination .next a, [rel='next'], button.next"

        try:
            element = self.actions.find_element(By.CSS_SELECTOR, selector, timeout=5)
            if element and element.is_enabled():
                # Check if it's disabled via class or attribute
                classes = element.get_attribute("class") or ""
                if "disabled" in classes.lower():
                    return False

                aria_disabled = element.get_attribute("aria-disabled")
                if aria_disabled == "true":
                    return False

                self.actions.click(element=element)
                self.actions.wait_for_page_load()
                return True
        except Exception as e:
            logger.debug(f"Next button navigation failed: {e}")

        return False

    def _navigate_page_number(self, selector: str | None) -> bool:
        """Navigate using page number links.

        Args:
            selector: CSS selector for page number links

        Returns:
            True if navigation successful
        """
        if not selector:
            selector = ".pagination a, .pager a, .page-numbers a"

        try:
            next_page = self._current_page + 1
            # Try to find link with page number
            page_links = self.actions.find_elements(By.CSS_SELECTOR, selector)

            for link in page_links:
                text = link.text.strip()
                href = link.get_attribute("href") or ""

                # Check if this is the next page link
                if text == str(next_page) or f"page={next_page}" in href or f"page/{next_page}" in href:
                    self.actions.click(element=link)
                    self.actions.wait_for_page_load()
                    return True

        except Exception as e:
            logger.debug(f"Page number navigation failed: {e}")

        return False

    def _navigate_infinite_scroll(self, scroll_pause: float = 2.0) -> bool:
        """Navigate using infinite scroll.

        Args:
            scroll_pause: Pause after scrolling

        Returns:
            True if more content loaded
        """
        try:
            # Get current scroll height
            last_height = self.driver.execute_script("return document.body.scrollHeight")

            # Scroll to bottom
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(scroll_pause)

            # Check if more content loaded
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            return new_height > last_height

        except Exception as e:
            logger.debug(f"Infinite scroll navigation failed: {e}")

        return False

    def _navigate_load_more(self, selector: str | None) -> bool:
        """Navigate using load more button.

        Args:
            selector: CSS selector for load more button

        Returns:
            True if navigation successful
        """
        if not selector:
            selector = ".load-more, button.more, [data-action='load-more']"

        try:
            element = self.actions.find_element(By.CSS_SELECTOR, selector, timeout=5)
            if element and element.is_displayed():
                # Get current item count
                old_count = len(self.driver.find_elements(By.CSS_SELECTOR, "*"))

                self.actions.click(element=element)
                time.sleep(self.page_delay)

                # Check if new items loaded
                new_count = len(self.driver.find_elements(By.CSS_SELECTOR, "*"))
                return new_count > old_count

        except Exception as e:
            logger.debug(f"Load more navigation failed: {e}")

        return False

    def _navigate_url_param(self, param_name: str = "page", base_url: str | None = None) -> bool:
        """Navigate by modifying URL parameter.

        Args:
            param_name: URL parameter name for page
            base_url: Base URL (uses current if not provided)

        Returns:
            True if navigation successful
        """
        try:
            current_url = base_url or self.driver.current_url
            parsed = urlparse(current_url)
            params = parse_qs(parsed.query)

            # Update page parameter
            next_page = self._current_page + 1
            params[param_name] = [str(next_page)]

            # Rebuild URL
            new_query = urlencode(params, doseq=True)
            new_url = urlunparse(
                (parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment)
            )

            self.driver.get(new_url)
            self.actions.wait_for_page_load()
            return True

        except Exception as e:
            logger.debug(f"URL param navigation failed: {e}")

        return False

    def detect_pagination_type(self) -> PaginationType | None:
        """Auto-detect pagination type on current page.

        Returns:
            Detected pagination type or None
        """
        # Check for next button
        next_selectors = [
            "a.next",
            ".pagination .next",
            "[rel='next']",
            "button.next",
            ".pager-next",
        ]
        for selector in next_selectors:
            if self.actions.is_element_present(By.CSS_SELECTOR, selector):
                logger.debug("Detected pagination type: NEXT_BUTTON")
                return PaginationType.NEXT_BUTTON

        # Check for page numbers
        page_selectors = [
            ".pagination a",
            ".pager a",
            ".page-numbers",
        ]
        for selector in page_selectors:
            elements = self.actions.find_elements(By.CSS_SELECTOR, selector, wait=False)
            if len(elements) > 2:
                logger.debug("Detected pagination type: PAGE_NUMBERS")
                return PaginationType.PAGE_NUMBERS

        # Check for load more button
        load_more_selectors = [
            ".load-more",
            "button.more",
            "[data-action='load-more']",
        ]
        for selector in load_more_selectors:
            if self.actions.is_element_present(By.CSS_SELECTOR, selector):
                logger.debug("Detected pagination type: LOAD_MORE")
                return PaginationType.LOAD_MORE

        # Check URL for page parameter
        current_url = self.driver.current_url
        if re.search(r"[?&]page=\d+", current_url):
            logger.debug("Detected pagination type: URL_PARAM")
            return PaginationType.URL_PARAM

        logger.debug("Could not detect pagination type")
        return None

    def get_total_pages(self, selector: str | None = None) -> int | None:
        """Try to detect total number of pages.

        Args:
            selector: CSS selector for pagination info

        Returns:
            Total pages or None if not detectable
        """
        try:
            # Try common patterns
            patterns = [
                r"Page \d+ of (\d+)",
                r"(\d+) pages",
                r"of (\d+)",
            ]

            # Check pagination text
            text_selectors = [
                ".pagination-info",
                ".page-info",
                ".pager-info",
            ]

            for sel in text_selectors:
                element = self.actions.find_element(By.CSS_SELECTOR, sel, wait=False)
                if element:
                    text = element.text
                    for pattern in patterns:
                        match = re.search(pattern, text, re.IGNORECASE)
                        if match:
                            return int(match.group(1))

            # Try finding highest page number in pagination links
            page_links = self.actions.find_elements(
                By.CSS_SELECTOR,
                ".pagination a, .pager a",
                wait=False,
            )
            max_page = 1
            for link in page_links:
                text = link.text.strip()
                if text.isdigit():
                    max_page = max(max_page, int(text))

            if max_page > 1:
                return max_page

        except Exception as e:
            logger.debug(f"Could not detect total pages: {e}")

        return None
