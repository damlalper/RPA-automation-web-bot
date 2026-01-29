"""Proxy rotation strategies."""

import random
from abc import ABC, abstractmethod
from enum import Enum
from typing import TYPE_CHECKING

from src.monitoring.logger import get_logger

if TYPE_CHECKING:
    from .manager import Proxy, ProxyManager

logger = get_logger(__name__)


class RotationStrategy(str, Enum):
    """Available rotation strategies."""

    ROUND_ROBIN = "round_robin"
    RANDOM = "random"
    LEAST_USED = "least_used"
    FASTEST = "fastest"
    WEIGHTED = "weighted"


class BaseRotator(ABC):
    """Base class for rotation strategies."""

    @abstractmethod
    def get_next(self, proxies: list["Proxy"]) -> "Proxy | None":
        """Get next proxy according to strategy.

        Args:
            proxies: List of available proxies

        Returns:
            Selected proxy or None
        """
        pass


class RoundRobinRotator(BaseRotator):
    """Round-robin rotation - cycle through proxies in order."""

    def __init__(self) -> None:
        self._index = 0

    def get_next(self, proxies: list["Proxy"]) -> "Proxy | None":
        """Get next proxy in round-robin order.

        Args:
            proxies: List of available proxies

        Returns:
            Next proxy or None
        """
        if not proxies:
            return None

        # Reset index if out of bounds
        if self._index >= len(proxies):
            self._index = 0

        proxy = proxies[self._index]
        self._index = (self._index + 1) % len(proxies)
        return proxy


class RandomRotator(BaseRotator):
    """Random rotation - select proxy randomly."""

    def get_next(self, proxies: list["Proxy"]) -> "Proxy | None":
        """Get random proxy.

        Args:
            proxies: List of available proxies

        Returns:
            Random proxy or None
        """
        if not proxies:
            return None
        return random.choice(proxies)


class LeastUsedRotator(BaseRotator):
    """Least used rotation - prefer proxies with fewer requests."""

    def get_next(self, proxies: list["Proxy"]) -> "Proxy | None":
        """Get least used proxy.

        Args:
            proxies: List of available proxies

        Returns:
            Least used proxy or None
        """
        if not proxies:
            return None
        return min(proxies, key=lambda p: p.total_requests)


class FastestRotator(BaseRotator):
    """Fastest rotation - prefer proxies with lowest response time."""

    def get_next(self, proxies: list["Proxy"]) -> "Proxy | None":
        """Get fastest proxy.

        Args:
            proxies: List of available proxies

        Returns:
            Fastest proxy or None
        """
        if not proxies:
            return None

        # Filter proxies with response time data
        with_time = [p for p in proxies if p.response_time is not None]

        if with_time:
            return min(with_time, key=lambda p: p.response_time)

        # Fallback to random if no timing data
        return random.choice(proxies)


class WeightedRotator(BaseRotator):
    """Weighted rotation - prefer proxies with higher success rate."""

    def get_next(self, proxies: list["Proxy"]) -> "Proxy | None":
        """Get proxy weighted by success rate.

        Args:
            proxies: List of available proxies

        Returns:
            Weighted proxy or None
        """
        if not proxies:
            return None

        # Calculate weights based on success rate
        weights = []
        for proxy in proxies:
            if proxy.total_requests == 0:
                weights.append(50.0)  # Default weight for unused proxies
            else:
                weights.append(max(proxy.success_rate, 1.0))  # Minimum weight of 1

        # Weighted random selection
        total_weight = sum(weights)
        r = random.uniform(0, total_weight)

        cumulative = 0
        for proxy, weight in zip(proxies, weights):
            cumulative += weight
            if r <= cumulative:
                return proxy

        return proxies[-1]


class ProxyRotator:
    """Main proxy rotator with configurable strategies."""

    def __init__(self, manager: "ProxyManager", strategy: RotationStrategy = RotationStrategy.ROUND_ROBIN) -> None:
        """Initialize proxy rotator.

        Args:
            manager: ProxyManager instance
            strategy: Rotation strategy to use
        """
        self.manager = manager
        self._strategy = strategy
        self._rotators: dict[RotationStrategy, BaseRotator] = {
            RotationStrategy.ROUND_ROBIN: RoundRobinRotator(),
            RotationStrategy.RANDOM: RandomRotator(),
            RotationStrategy.LEAST_USED: LeastUsedRotator(),
            RotationStrategy.FASTEST: FastestRotator(),
            RotationStrategy.WEIGHTED: WeightedRotator(),
        }
        self._current_proxy: "Proxy | None" = None

    @property
    def strategy(self) -> RotationStrategy:
        """Get current rotation strategy.

        Returns:
            Current strategy
        """
        return self._strategy

    @strategy.setter
    def strategy(self, value: RotationStrategy) -> None:
        """Set rotation strategy.

        Args:
            value: New strategy
        """
        self._strategy = value
        logger.info(f"Rotation strategy changed to: {value.value}")

    @property
    def current_proxy(self) -> "Proxy | None":
        """Get current proxy.

        Returns:
            Current proxy or None
        """
        return self._current_proxy

    def get_next(self) -> "Proxy | None":
        """Get next proxy according to current strategy.

        Returns:
            Next proxy or None if disabled/empty
        """
        if not self.manager.enabled:
            logger.debug("Proxy rotation disabled, returning None")
            return None

        healthy_proxies = self.manager.get_healthy()
        if not healthy_proxies:
            logger.warning("No healthy proxies available")
            return None

        rotator = self._rotators.get(self._strategy, self._rotators[RotationStrategy.ROUND_ROBIN])
        proxy = rotator.get_next(healthy_proxies)

        if proxy:
            self._current_proxy = proxy
            logger.debug(f"Selected proxy: {proxy.url_no_auth} | strategy={self._strategy.value}")

        return proxy

    def rotate(self) -> "Proxy | None":
        """Force rotation to next proxy.

        Returns:
            New proxy or None
        """
        return self.get_next()

    def record_success(self, response_time: float | None = None) -> None:
        """Record successful request with current proxy.

        Args:
            response_time: Response time in seconds
        """
        if self._current_proxy:
            self._current_proxy.record_success(response_time)
            logger.debug(f"Recorded success for proxy: {self._current_proxy.url_no_auth}")

    def record_failure(self, auto_rotate: bool = True) -> "Proxy | None":
        """Record failed request with current proxy.

        Args:
            auto_rotate: Automatically rotate to next proxy

        Returns:
            New proxy if auto_rotate, else None
        """
        if self._current_proxy:
            self._current_proxy.record_failure()
            logger.debug(f"Recorded failure for proxy: {self._current_proxy.url_no_auth}")

            # Mark as unhealthy if too many failures
            if self._current_proxy.total_requests >= 5 and self._current_proxy.success_rate < 20:
                self.manager.mark_unhealthy(self._current_proxy)

        if auto_rotate:
            return self.get_next()
        return None

    def mark_current_unhealthy(self, auto_rotate: bool = True) -> "Proxy | None":
        """Mark current proxy as unhealthy.

        Args:
            auto_rotate: Automatically rotate to next proxy

        Returns:
            New proxy if auto_rotate, else None
        """
        if self._current_proxy:
            self.manager.mark_unhealthy(self._current_proxy)
            self._current_proxy = None

        if auto_rotate:
            return self.get_next()
        return None

    def get_proxy_for_selenium(self) -> str | None:
        """Get proxy URL formatted for Selenium.

        Returns:
            Proxy URL or None
        """
        proxy = self.get_next()
        if proxy:
            # Selenium expects format: host:port for basic or http://user:pass@host:port
            if proxy.username and proxy.password:
                return proxy.url
            return f"{proxy.address}:{proxy.port}"
        return None

    def get_proxy_dict(self) -> dict[str, str] | None:
        """Get proxy as dictionary for requests library.

        Returns:
            Proxy dict or None
        """
        proxy = self.get_next()
        if proxy:
            return {
                "http": proxy.url,
                "https": proxy.url,
            }
        return None
