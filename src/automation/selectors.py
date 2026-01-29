"""Selector management with fallback support."""

from dataclasses import dataclass, field
from typing import Any

from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement

from src.monitoring.logger import get_logger

logger = get_logger(__name__)


@dataclass
class Selector:
    """Represents a single selector with fallbacks."""

    name: str
    primary: tuple[By, str]
    fallbacks: list[tuple[By, str]] = field(default_factory=list)
    description: str = ""

    def all_selectors(self) -> list[tuple[By, str]]:
        """Get all selectors including fallbacks.

        Returns:
            List of (By, value) tuples
        """
        return [self.primary] + self.fallbacks

    @classmethod
    def css(cls, name: str, selector: str, fallbacks: list[str] | None = None, description: str = "") -> "Selector":
        """Create CSS selector.

        Args:
            name: Selector name
            selector: Primary CSS selector
            fallbacks: Fallback CSS selectors
            description: Selector description

        Returns:
            Selector instance
        """
        fb = [(By.CSS_SELECTOR, s) for s in (fallbacks or [])]
        return cls(name=name, primary=(By.CSS_SELECTOR, selector), fallbacks=fb, description=description)

    @classmethod
    def xpath(cls, name: str, selector: str, fallbacks: list[str] | None = None, description: str = "") -> "Selector":
        """Create XPath selector.

        Args:
            name: Selector name
            selector: Primary XPath selector
            fallbacks: Fallback XPath selectors
            description: Selector description

        Returns:
            Selector instance
        """
        fb = [(By.XPATH, s) for s in (fallbacks or [])]
        return cls(name=name, primary=(By.XPATH, selector), fallbacks=fb, description=description)

    @classmethod
    def id(cls, name: str, element_id: str, fallbacks: list[str] | None = None, description: str = "") -> "Selector":
        """Create ID selector.

        Args:
            name: Selector name
            element_id: Element ID
            fallbacks: Fallback IDs
            description: Selector description

        Returns:
            Selector instance
        """
        fb = [(By.ID, s) for s in (fallbacks or [])]
        return cls(name=name, primary=(By.ID, element_id), fallbacks=fb, description=description)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Selector":
        """Create selector from dictionary.

        Args:
            data: Dictionary with selector data

        Returns:
            Selector instance
        """
        by_map = {
            "css": By.CSS_SELECTOR,
            "xpath": By.XPATH,
            "id": By.ID,
            "class": By.CLASS_NAME,
            "name": By.NAME,
            "tag": By.TAG_NAME,
            "link_text": By.LINK_TEXT,
            "partial_link_text": By.PARTIAL_LINK_TEXT,
        }

        by_type = by_map.get(data.get("type", "css"), By.CSS_SELECTOR)
        primary = (by_type, data["selector"])

        fallbacks = []
        for fb in data.get("fallbacks", []):
            fb_type = by_map.get(fb.get("type", "css"), By.CSS_SELECTOR)
            fallbacks.append((fb_type, fb["selector"]))

        return cls(
            name=data["name"],
            primary=primary,
            fallbacks=fallbacks,
            description=data.get("description", ""),
        )


class SelectorManager:
    """Manages selectors with fallback resolution."""

    def __init__(self, driver: WebDriver) -> None:
        """Initialize selector manager.

        Args:
            driver: Selenium WebDriver instance
        """
        self.driver = driver
        self._selectors: dict[str, Selector] = {}
        self._cache: dict[str, tuple[By, str]] = {}  # Cache successful selectors

    def register(self, selector: Selector) -> None:
        """Register a selector.

        Args:
            selector: Selector to register
        """
        self._selectors[selector.name] = selector
        logger.debug(f"Registered selector: {selector.name}")

    def register_many(self, selectors: list[Selector]) -> None:
        """Register multiple selectors.

        Args:
            selectors: List of selectors
        """
        for selector in selectors:
            self.register(selector)

    def register_from_dict(self, config: dict[str, Any]) -> None:
        """Register selectors from dictionary config.

        Args:
            config: Dictionary with selectors configuration
        """
        for name, data in config.items():
            if isinstance(data, dict):
                data["name"] = name
                self.register(Selector.from_dict(data))

    def get(self, name: str) -> Selector | None:
        """Get selector by name.

        Args:
            name: Selector name

        Returns:
            Selector or None
        """
        return self._selectors.get(name)

    def find_element(
        self,
        name: str,
        timeout: float = 10,
        use_cache: bool = True,
    ) -> WebElement | None:
        """Find element using selector with fallback.

        Args:
            name: Selector name
            timeout: Wait timeout per selector
            use_cache: Use cached successful selector

        Returns:
            WebElement or None
        """
        selector = self._selectors.get(name)
        if not selector:
            logger.warning(f"Selector not found: {name}")
            return None

        # Try cached selector first
        if use_cache and name in self._cache:
            by, value = self._cache[name]
            try:
                from selenium.webdriver.support.ui import WebDriverWait
                from selenium.webdriver.support import expected_conditions as EC

                element = WebDriverWait(self.driver, timeout / 2).until(
                    EC.presence_of_element_located((by, value))
                )
                logger.debug(f"Found element using cached selector: {name}")
                return element
            except Exception:
                del self._cache[name]  # Clear invalid cache

        # Try all selectors
        for by, value in selector.all_selectors():
            try:
                from selenium.webdriver.support.ui import WebDriverWait
                from selenium.webdriver.support import expected_conditions as EC

                element = WebDriverWait(self.driver, timeout).until(
                    EC.presence_of_element_located((by, value))
                )

                # Cache successful selector
                self._cache[name] = (by, value)
                logger.debug(f"Found element: {name} | by={by} | value={value}")
                return element

            except Exception:
                logger.debug(f"Selector failed: {name} | by={by} | value={value}")
                continue

        logger.warning(f"Element not found with any selector: {name}")
        return None

    def find_elements(
        self,
        name: str,
        timeout: float = 10,
        use_cache: bool = True,
    ) -> list[WebElement]:
        """Find multiple elements using selector with fallback.

        Args:
            name: Selector name
            timeout: Wait timeout per selector
            use_cache: Use cached successful selector

        Returns:
            List of WebElements
        """
        selector = self._selectors.get(name)
        if not selector:
            logger.warning(f"Selector not found: {name}")
            return []

        # Try cached selector first
        if use_cache and name in self._cache:
            by, value = self._cache[name]
            try:
                from selenium.webdriver.support.ui import WebDriverWait
                from selenium.webdriver.support import expected_conditions as EC

                elements = WebDriverWait(self.driver, timeout / 2).until(
                    EC.presence_of_all_elements_located((by, value))
                )
                if elements:
                    return elements
            except Exception:
                del self._cache[name]

        # Try all selectors
        for by, value in selector.all_selectors():
            try:
                from selenium.webdriver.support.ui import WebDriverWait
                from selenium.webdriver.support import expected_conditions as EC

                elements = WebDriverWait(self.driver, timeout).until(
                    EC.presence_of_all_elements_located((by, value))
                )

                if elements:
                    self._cache[name] = (by, value)
                    logger.debug(f"Found {len(elements)} elements: {name}")
                    return elements

            except Exception:
                continue

        logger.warning(f"No elements found with any selector: {name}")
        return []

    def clear_cache(self) -> None:
        """Clear selector cache."""
        self._cache.clear()
        logger.debug("Selector cache cleared")

    def validate_selectors(self) -> dict[str, bool]:
        """Validate all registered selectors.

        Returns:
            Dictionary of selector name -> found status
        """
        results = {}
        for name in self._selectors:
            element = self.find_element(name, timeout=5, use_cache=False)
            results[name] = element is not None
        return results


# Predefined common selectors
COMMON_SELECTORS = {
    "login_form": Selector.css(
        name="login_form",
        selector="form[action*='login'], form#login, form.login-form",
        fallbacks=["#loginForm", ".login-container form"],
        description="Login form element",
    ),
    "username_input": Selector.css(
        name="username_input",
        selector="input[name='username'], input[name='email'], input#username",
        fallbacks=["input[type='email']", "input.username-input"],
        description="Username/email input field",
    ),
    "password_input": Selector.css(
        name="password_input",
        selector="input[name='password'], input#password, input[type='password']",
        fallbacks=[".password-input"],
        description="Password input field",
    ),
    "submit_button": Selector.css(
        name="submit_button",
        selector="button[type='submit'], input[type='submit']",
        fallbacks=["button.submit", ".btn-submit", "#submit"],
        description="Form submit button",
    ),
    "pagination_next": Selector.css(
        name="pagination_next",
        selector="a.next, a[rel='next'], .pagination .next a",
        fallbacks=["button.next", "li.next a", "[aria-label='Next']"],
        description="Next page pagination link",
    ),
    "pagination_prev": Selector.css(
        name="pagination_prev",
        selector="a.prev, a[rel='prev'], .pagination .prev a",
        fallbacks=["button.prev", "li.prev a", "[aria-label='Previous']"],
        description="Previous page pagination link",
    ),
}
