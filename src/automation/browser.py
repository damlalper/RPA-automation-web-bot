"""Selenium browser factory and management."""

from contextlib import contextmanager
from typing import Generator

from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.remote.webdriver import WebDriver
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.firefox import GeckoDriverManager
from webdriver_manager.microsoft import EdgeChromiumDriverManager

from src.core.config import BrowserType, settings
from src.monitoring.logger import get_logger

logger = get_logger(__name__)


class BrowserFactory:
    """Factory for creating Selenium WebDriver instances."""

    @staticmethod
    def _get_chrome_options(
        headless: bool = True,
        proxy: str | None = None,
        user_agent: str | None = None,
    ) -> ChromeOptions:
        """Configure Chrome options.

        Args:
            headless: Run in headless mode
            proxy: Proxy server address
            user_agent: Custom user agent

        Returns:
            Configured ChromeOptions
        """
        options = ChromeOptions()

        if headless:
            options.add_argument("--headless=new")

        # Performance and stability
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-infobars")
        options.add_argument("--disable-notifications")
        options.add_argument("--disable-popup-blocking")

        # Window size
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--start-maximized")

        # Anti-detection
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        # Proxy
        if proxy:
            options.add_argument(f"--proxy-server={proxy}")

        # User agent
        if user_agent:
            options.add_argument(f"--user-agent={user_agent}")
        else:
            options.add_argument(
                "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )

        # Logging
        options.add_argument("--log-level=3")
        options.add_experimental_option(
            "prefs",
            {
                "profile.default_content_setting_values.notifications": 2,
                "credentials_enable_service": False,
                "profile.password_manager_enabled": False,
            },
        )

        return options

    @staticmethod
    def _get_firefox_options(
        headless: bool = True,
        proxy: str | None = None,
        user_agent: str | None = None,
    ) -> FirefoxOptions:
        """Configure Firefox options.

        Args:
            headless: Run in headless mode
            proxy: Proxy server address
            user_agent: Custom user agent

        Returns:
            Configured FirefoxOptions
        """
        options = FirefoxOptions()

        if headless:
            options.add_argument("--headless")

        # Window size
        options.add_argument("--width=1920")
        options.add_argument("--height=1080")

        # User agent
        if user_agent:
            options.set_preference("general.useragent.override", user_agent)

        # Disable various features
        options.set_preference("dom.webnotifications.enabled", False)
        options.set_preference("dom.push.enabled", False)

        return options

    @staticmethod
    def _get_edge_options(
        headless: bool = True,
        proxy: str | None = None,
        user_agent: str | None = None,
    ) -> EdgeOptions:
        """Configure Edge options.

        Args:
            headless: Run in headless mode
            proxy: Proxy server address
            user_agent: Custom user agent

        Returns:
            Configured EdgeOptions
        """
        options = EdgeOptions()

        if headless:
            options.add_argument("--headless=new")

        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")

        if proxy:
            options.add_argument(f"--proxy-server={proxy}")

        if user_agent:
            options.add_argument(f"--user-agent={user_agent}")

        return options

    @classmethod
    def create(
        cls,
        browser_type: BrowserType | None = None,
        headless: bool | None = None,
        proxy: str | None = None,
        user_agent: str | None = None,
    ) -> WebDriver:
        """Create a new WebDriver instance.

        Args:
            browser_type: Type of browser to use
            headless: Run in headless mode (uses settings if None)
            proxy: Proxy server address
            user_agent: Custom user agent

        Returns:
            Configured WebDriver instance
        """
        browser_type = browser_type or settings.browser_type
        headless = headless if headless is not None else settings.selenium_headless

        logger.info(f"Creating browser | type={browser_type.value} | headless={headless}")

        if browser_type == BrowserType.CHROME:
            options = cls._get_chrome_options(headless, proxy, user_agent)
            service = ChromeService(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)

        elif browser_type == BrowserType.FIREFOX:
            options = cls._get_firefox_options(headless, proxy, user_agent)
            service = FirefoxService(GeckoDriverManager().install())
            driver = webdriver.Firefox(service=service, options=options)

        elif browser_type == BrowserType.EDGE:
            options = cls._get_edge_options(headless, proxy, user_agent)
            service = EdgeService(EdgeChromiumDriverManager().install())
            driver = webdriver.Edge(service=service, options=options)

        else:
            raise ValueError(f"Unsupported browser type: {browser_type}")

        # Configure timeouts
        driver.set_page_load_timeout(settings.selenium_timeout)
        driver.implicitly_wait(settings.selenium_implicit_wait)

        # Anti-detection scripts for Chrome/Edge
        if browser_type in [BrowserType.CHROME, BrowserType.EDGE]:
            driver.execute_cdp_cmd(
                "Page.addScriptToEvaluateOnNewDocument",
                {
                    "source": """
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                    Object.defineProperty(navigator, 'plugins', {
                        get: () => [1, 2, 3, 4, 5]
                    });
                    Object.defineProperty(navigator, 'languages', {
                        get: () => ['en-US', 'en']
                    });
                    """
                },
            )

        logger.info(f"Browser created successfully | session_id={driver.session_id}")
        return driver


class BrowserManager:
    """Manager for browser lifecycle and operations."""

    def __init__(
        self,
        browser_type: BrowserType | None = None,
        headless: bool | None = None,
        proxy: str | None = None,
    ) -> None:
        """Initialize browser manager.

        Args:
            browser_type: Type of browser to use
            headless: Run in headless mode
            proxy: Proxy server address
        """
        self.browser_type = browser_type or settings.browser_type
        self.headless = headless if headless is not None else settings.selenium_headless
        self.proxy = proxy
        self._driver: WebDriver | None = None

    @property
    def driver(self) -> WebDriver:
        """Get or create WebDriver instance.

        Returns:
            WebDriver instance

        Raises:
            RuntimeError: If browser not initialized
        """
        if self._driver is None:
            raise RuntimeError("Browser not initialized. Call start() first.")
        return self._driver

    @property
    def is_active(self) -> bool:
        """Check if browser is active.

        Returns:
            True if browser is active
        """
        if self._driver is None:
            return False
        try:
            _ = self._driver.current_url
            return True
        except Exception:
            return False

    def start(self) -> WebDriver:
        """Start browser session.

        Returns:
            WebDriver instance
        """
        if self._driver is not None:
            logger.warning("Browser already started, returning existing instance")
            return self._driver

        self._driver = BrowserFactory.create(
            browser_type=self.browser_type,
            headless=self.headless,
            proxy=self.proxy,
        )
        return self._driver

    def stop(self) -> None:
        """Stop browser session."""
        if self._driver is not None:
            try:
                session_id = self._driver.session_id
                self._driver.quit()
                logger.info(f"Browser closed | session_id={session_id}")
            except Exception as e:
                logger.error(f"Error closing browser: {e}")
            finally:
                self._driver = None

    def restart(self) -> WebDriver:
        """Restart browser session.

        Returns:
            New WebDriver instance
        """
        self.stop()
        return self.start()

    def set_proxy(self, proxy: str | None) -> None:
        """Set proxy and restart browser.

        Args:
            proxy: New proxy address or None to disable
        """
        self.proxy = proxy
        if self._driver is not None:
            self.restart()

    def navigate(self, url: str) -> None:
        """Navigate to URL.

        Args:
            url: Target URL
        """
        logger.debug(f"Navigating to: {url}")
        self.driver.get(url)

    def get_current_url(self) -> str:
        """Get current URL.

        Returns:
            Current page URL
        """
        return self.driver.current_url

    def get_page_source(self) -> str:
        """Get current page source.

        Returns:
            Page HTML source
        """
        return self.driver.page_source

    def take_screenshot(self, filepath: str) -> bool:
        """Take screenshot of current page.

        Args:
            filepath: Path to save screenshot

        Returns:
            True if successful
        """
        try:
            self.driver.save_screenshot(filepath)
            logger.debug(f"Screenshot saved: {filepath}")
            return True
        except Exception as e:
            logger.error(f"Failed to take screenshot: {e}")
            return False

    def execute_script(self, script: str, *args) -> any:
        """Execute JavaScript in browser.

        Args:
            script: JavaScript code
            *args: Script arguments

        Returns:
            Script result
        """
        return self.driver.execute_script(script, *args)

    def __enter__(self) -> "BrowserManager":
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.stop()


@contextmanager
def browser_session(
    browser_type: BrowserType | None = None,
    headless: bool | None = None,
    proxy: str | None = None,
) -> Generator[BrowserManager, None, None]:
    """Context manager for browser sessions.

    Args:
        browser_type: Type of browser to use
        headless: Run in headless mode
        proxy: Proxy server address

    Yields:
        BrowserManager instance
    """
    manager = BrowserManager(browser_type, headless, proxy)
    try:
        manager.start()
        yield manager
    finally:
        manager.stop()
