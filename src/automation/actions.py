"""Automation actions for web interactions."""

import random
import time
from typing import Any

from selenium.common.exceptions import (
    ElementClickInterceptedException,
    ElementNotInteractableException,
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.select import Select
from selenium.webdriver.support.ui import WebDriverWait

from src.core.config import settings
from src.monitoring.logger import get_logger

logger = get_logger(__name__)


class AutomationActions:
    """High-level automation actions for web interactions."""

    def __init__(self, driver: WebDriver) -> None:
        """Initialize automation actions.

        Args:
            driver: Selenium WebDriver instance
        """
        self.driver = driver
        self._default_timeout = settings.selenium_timeout

    def wait_for_element(
        self,
        by: By,
        value: str,
        timeout: float | None = None,
        condition: str = "presence",
    ) -> WebElement:
        """Wait for element to be present/visible/clickable.

        Args:
            by: Locator strategy (By.ID, By.CSS_SELECTOR, etc.)
            value: Locator value
            timeout: Wait timeout in seconds
            condition: Wait condition (presence, visible, clickable)

        Returns:
            WebElement when found

        Raises:
            TimeoutException: If element not found within timeout
        """
        timeout = timeout or self._default_timeout
        wait = WebDriverWait(self.driver, timeout)

        conditions = {
            "presence": EC.presence_of_element_located,
            "visible": EC.visibility_of_element_located,
            "clickable": EC.element_to_be_clickable,
            "invisible": EC.invisibility_of_element_located,
        }

        ec_func = conditions.get(condition, EC.presence_of_element_located)
        return wait.until(ec_func((by, value)))

    def wait_for_elements(
        self,
        by: By,
        value: str,
        timeout: float | None = None,
        condition: str = "presence",
    ) -> list[WebElement]:
        """Wait for multiple elements.

        Args:
            by: Locator strategy
            value: Locator value
            timeout: Wait timeout in seconds
            condition: Wait condition

        Returns:
            List of WebElements
        """
        timeout = timeout or self._default_timeout
        wait = WebDriverWait(self.driver, timeout)

        conditions = {
            "presence": EC.presence_of_all_elements_located,
            "visible": EC.visibility_of_all_elements_located,
        }

        ec_func = conditions.get(condition, EC.presence_of_all_elements_located)
        return wait.until(ec_func((by, value)))

    def find_element(
        self,
        by: By,
        value: str,
        wait: bool = True,
        timeout: float | None = None,
    ) -> WebElement | None:
        """Find element with optional wait.

        Args:
            by: Locator strategy
            value: Locator value
            wait: Whether to wait for element
            timeout: Wait timeout in seconds

        Returns:
            WebElement or None if not found
        """
        try:
            if wait:
                return self.wait_for_element(by, value, timeout)
            return self.driver.find_element(by, value)
        except (NoSuchElementException, TimeoutException) as e:
            logger.debug(f"Element not found: {by}={value} | {e}")
            return None

    def find_elements(
        self,
        by: By,
        value: str,
        wait: bool = True,
        timeout: float | None = None,
    ) -> list[WebElement]:
        """Find multiple elements with optional wait.

        Args:
            by: Locator strategy
            value: Locator value
            wait: Whether to wait for elements
            timeout: Wait timeout in seconds

        Returns:
            List of WebElements (empty if none found)
        """
        try:
            if wait:
                return self.wait_for_elements(by, value, timeout)
            return self.driver.find_elements(by, value)
        except (NoSuchElementException, TimeoutException):
            return []

    def click(
        self,
        element: WebElement | None = None,
        by: By | None = None,
        value: str | None = None,
        timeout: float | None = None,
        retry: int = 3,
    ) -> bool:
        """Click element with retry logic.

        Args:
            element: WebElement to click (or use by/value)
            by: Locator strategy
            value: Locator value
            timeout: Wait timeout
            retry: Number of retry attempts

        Returns:
            True if clicked successfully
        """
        for attempt in range(retry):
            try:
                if element is None:
                    if by is None or value is None:
                        raise ValueError("Must provide element or (by, value)")
                    element = self.wait_for_element(by, value, timeout, condition="clickable")

                # Scroll into view
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center'});", element
                )
                time.sleep(0.2)

                element.click()
                logger.debug(f"Clicked element successfully")
                return True

            except ElementClickInterceptedException:
                logger.debug(f"Click intercepted, trying JavaScript click (attempt {attempt + 1})")
                try:
                    self.driver.execute_script("arguments[0].click();", element)
                    return True
                except Exception:
                    pass

            except (StaleElementReferenceException, ElementNotInteractableException) as e:
                logger.debug(f"Click failed (attempt {attempt + 1}): {e}")
                if by and value:
                    element = None  # Re-find element on next attempt
                time.sleep(0.5)

            except Exception as e:
                logger.warning(f"Click error: {e}")
                return False

        logger.warning("Click failed after all retries")
        return False

    def fill_input(
        self,
        element: WebElement | None = None,
        by: By | None = None,
        value: str | None = None,
        text: str = "",
        clear_first: bool = True,
        human_like: bool = False,
    ) -> bool:
        """Fill input field with text.

        Args:
            element: WebElement to fill (or use by/value)
            by: Locator strategy
            value: Locator value
            text: Text to input
            clear_first: Clear existing text first
            human_like: Type with random delays (anti-detection)

        Returns:
            True if filled successfully
        """
        try:
            if element is None:
                if by is None or value is None:
                    raise ValueError("Must provide element or (by, value)")
                element = self.wait_for_element(by, value, condition="visible")

            # Scroll into view and focus
            self.driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center'});", element
            )
            element.click()

            if clear_first:
                element.clear()
                # Fallback clear with keyboard
                element.send_keys(Keys.CONTROL + "a")
                element.send_keys(Keys.DELETE)

            if human_like:
                for char in text:
                    element.send_keys(char)
                    time.sleep(random.uniform(0.05, 0.15))
            else:
                element.send_keys(text)

            logger.debug(f"Filled input with text (length={len(text)})")
            return True

        except Exception as e:
            logger.warning(f"Fill input failed: {e}")
            return False

    def select_dropdown(
        self,
        element: WebElement | None = None,
        by: By | None = None,
        value: str | None = None,
        select_by: str = "value",
        select_value: str = "",
    ) -> bool:
        """Select option from dropdown.

        Args:
            element: Select element (or use by/value)
            by: Locator strategy
            value: Locator value
            select_by: Selection method (value, text, index)
            select_value: Value to select

        Returns:
            True if selected successfully
        """
        try:
            if element is None:
                if by is None or value is None:
                    raise ValueError("Must provide element or (by, value)")
                element = self.wait_for_element(by, value)

            select = Select(element)

            if select_by == "value":
                select.select_by_value(select_value)
            elif select_by == "text":
                select.select_by_visible_text(select_value)
            elif select_by == "index":
                select.select_by_index(int(select_value))
            else:
                raise ValueError(f"Invalid select_by: {select_by}")

            logger.debug(f"Selected dropdown option: {select_value}")
            return True

        except Exception as e:
            logger.warning(f"Select dropdown failed: {e}")
            return False

    def submit_form(
        self,
        form_element: WebElement | None = None,
        submit_button_by: By | None = None,
        submit_button_value: str | None = None,
    ) -> bool:
        """Submit a form.

        Args:
            form_element: Form element to submit
            submit_button_by: Locator for submit button
            submit_button_value: Submit button locator value

        Returns:
            True if submitted successfully
        """
        try:
            if submit_button_by and submit_button_value:
                return self.click(by=submit_button_by, value=submit_button_value)
            elif form_element:
                form_element.submit()
                logger.debug("Form submitted")
                return True
            else:
                raise ValueError("Must provide form_element or submit button locator")
        except Exception as e:
            logger.warning(f"Submit form failed: {e}")
            return False

    def hover(self, element: WebElement) -> bool:
        """Hover over element.

        Args:
            element: Element to hover

        Returns:
            True if successful
        """
        try:
            ActionChains(self.driver).move_to_element(element).perform()
            logger.debug("Hovered over element")
            return True
        except Exception as e:
            logger.warning(f"Hover failed: {e}")
            return False

    def scroll_to_bottom(self, pause: float = 0.5) -> None:
        """Scroll to page bottom.

        Args:
            pause: Pause between scrolls
        """
        last_height = self.driver.execute_script("return document.body.scrollHeight")

        while True:
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(pause)
            new_height = self.driver.execute_script("return document.body.scrollHeight")

            if new_height == last_height:
                break
            last_height = new_height

        logger.debug("Scrolled to bottom")

    def scroll_by(self, x: int = 0, y: int = 300) -> None:
        """Scroll by specified pixels.

        Args:
            x: Horizontal scroll
            y: Vertical scroll
        """
        self.driver.execute_script(f"window.scrollBy({x}, {y});")

    def wait_for_page_load(self, timeout: float | None = None) -> bool:
        """Wait for page to fully load.

        Args:
            timeout: Wait timeout

        Returns:
            True if page loaded
        """
        timeout = timeout or self._default_timeout
        try:
            WebDriverWait(self.driver, timeout).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            return True
        except TimeoutException:
            logger.warning("Page load timeout")
            return False

    def wait_for_ajax(self, timeout: float | None = None) -> bool:
        """Wait for AJAX requests to complete (jQuery).

        Args:
            timeout: Wait timeout

        Returns:
            True if AJAX completed
        """
        timeout = timeout or self._default_timeout
        try:
            WebDriverWait(self.driver, timeout).until(
                lambda d: d.execute_script("return jQuery.active == 0")
            )
            return True
        except Exception:
            return True  # jQuery might not be present

    def get_text(self, element: WebElement | None = None, by: By | None = None, value: str | None = None) -> str:
        """Get element text content.

        Args:
            element: WebElement (or use by/value)
            by: Locator strategy
            value: Locator value

        Returns:
            Element text or empty string
        """
        try:
            if element is None:
                if by is None or value is None:
                    return ""
                element = self.find_element(by, value)

            if element:
                return element.text.strip()
            return ""
        except Exception:
            return ""

    def get_attribute(
        self,
        attribute: str,
        element: WebElement | None = None,
        by: By | None = None,
        value: str | None = None,
    ) -> str | None:
        """Get element attribute value.

        Args:
            attribute: Attribute name
            element: WebElement (or use by/value)
            by: Locator strategy
            value: Locator value

        Returns:
            Attribute value or None
        """
        try:
            if element is None:
                if by is None or value is None:
                    return None
                element = self.find_element(by, value)

            if element:
                return element.get_attribute(attribute)
            return None
        except Exception:
            return None

    def is_element_present(self, by: By, value: str, timeout: float = 2) -> bool:
        """Check if element is present.

        Args:
            by: Locator strategy
            value: Locator value
            timeout: Wait timeout

        Returns:
            True if element is present
        """
        try:
            self.wait_for_element(by, value, timeout)
            return True
        except TimeoutException:
            return False

    def switch_to_iframe(self, iframe: WebElement | str) -> bool:
        """Switch to iframe.

        Args:
            iframe: WebElement or iframe name/id

        Returns:
            True if switched successfully
        """
        try:
            self.driver.switch_to.frame(iframe)
            logger.debug("Switched to iframe")
            return True
        except Exception as e:
            logger.warning(f"Switch to iframe failed: {e}")
            return False

    def switch_to_default_content(self) -> None:
        """Switch back to main document."""
        self.driver.switch_to.default_content()

    def switch_to_window(self, window_handle: str | None = None) -> bool:
        """Switch to window/tab.

        Args:
            window_handle: Window handle (None for last opened)

        Returns:
            True if switched successfully
        """
        try:
            if window_handle is None:
                window_handle = self.driver.window_handles[-1]
            self.driver.switch_to.window(window_handle)
            return True
        except Exception as e:
            logger.warning(f"Switch to window failed: {e}")
            return False

    def close_current_window(self) -> None:
        """Close current window/tab."""
        self.driver.close()

    def human_delay(self, min_sec: float = 0.5, max_sec: float = 2.0) -> None:
        """Add random human-like delay.

        Args:
            min_sec: Minimum delay
            max_sec: Maximum delay
        """
        delay = random.uniform(min_sec, max_sec)
        time.sleep(delay)

    def extract_table_data(self, table_element: WebElement) -> list[dict[str, Any]]:
        """Extract data from HTML table.

        Args:
            table_element: Table WebElement

        Returns:
            List of row dictionaries
        """
        data = []
        try:
            # Get headers
            headers = []
            header_row = table_element.find_elements(By.TAG_NAME, "th")
            if header_row:
                headers = [h.text.strip() for h in header_row]

            # Get rows
            rows = table_element.find_elements(By.TAG_NAME, "tr")
            for row in rows:
                cells = row.find_elements(By.TAG_NAME, "td")
                if cells:
                    if headers:
                        row_data = {headers[i]: cell.text.strip() for i, cell in enumerate(cells) if i < len(headers)}
                    else:
                        row_data = {f"col_{i}": cell.text.strip() for i, cell in enumerate(cells)}
                    data.append(row_data)

        except Exception as e:
            logger.warning(f"Extract table data failed: {e}")

        return data
