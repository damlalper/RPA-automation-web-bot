"""Proxy pool management."""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.core.config import settings
from src.monitoring.logger import get_logger

logger = get_logger(__name__)


@dataclass
class Proxy:
    """Represents a proxy server."""

    address: str
    port: int
    protocol: str = "http"
    username: str | None = None
    password: str | None = None
    country: str | None = None

    # Runtime stats
    is_healthy: bool = True
    response_time: float | None = None
    success_count: int = 0
    fail_count: int = 0
    total_requests: int = 0

    @property
    def url(self) -> str:
        """Get proxy URL.

        Returns:
            Formatted proxy URL
        """
        if self.username and self.password:
            return f"{self.protocol}://{self.username}:{self.password}@{self.address}:{self.port}"
        return f"{self.protocol}://{self.address}:{self.port}"

    @property
    def url_no_auth(self) -> str:
        """Get proxy URL without authentication.

        Returns:
            Proxy URL without credentials
        """
        return f"{self.protocol}://{self.address}:{self.port}"

    @property
    def success_rate(self) -> float:
        """Calculate success rate.

        Returns:
            Success rate percentage
        """
        if self.total_requests == 0:
            return 0.0
        return (self.success_count / self.total_requests) * 100

    def record_success(self, response_time: float | None = None) -> None:
        """Record successful request.

        Args:
            response_time: Response time in seconds
        """
        self.success_count += 1
        self.total_requests += 1
        if response_time is not None:
            self.response_time = response_time

    def record_failure(self) -> None:
        """Record failed request."""
        self.fail_count += 1
        self.total_requests += 1

    @classmethod
    def from_string(cls, proxy_str: str) -> "Proxy | None":
        """Parse proxy from string.

        Supported formats:
        - ip:port
        - ip:port:username:password
        - protocol://ip:port
        - protocol://username:password@ip:port

        Args:
            proxy_str: Proxy string

        Returns:
            Proxy instance or None if invalid
        """
        proxy_str = proxy_str.strip()
        if not proxy_str or proxy_str.startswith("#"):
            return None

        # URL format: protocol://[user:pass@]ip:port
        url_pattern = r"^(https?|socks[45]?)://(?:([^:]+):([^@]+)@)?([^:]+):(\d+)$"
        match = re.match(url_pattern, proxy_str)
        if match:
            return cls(
                protocol=match.group(1),
                username=match.group(2),
                password=match.group(3),
                address=match.group(4),
                port=int(match.group(5)),
            )

        # Simple format: ip:port or ip:port:user:pass
        parts = proxy_str.split(":")
        if len(parts) == 2:
            return cls(address=parts[0], port=int(parts[1]))
        elif len(parts) == 4:
            return cls(
                address=parts[0],
                port=int(parts[1]),
                username=parts[2],
                password=parts[3],
            )

        logger.warning(f"Invalid proxy format: {proxy_str}")
        return None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "address": self.address,
            "port": self.port,
            "protocol": self.protocol,
            "username": self.username,
            "country": self.country,
            "is_healthy": self.is_healthy,
            "response_time": self.response_time,
            "success_rate": self.success_rate,
            "total_requests": self.total_requests,
        }


@dataclass
class ProxyPool:
    """Pool of proxy servers."""

    proxies: list[Proxy] = field(default_factory=list)

    def add(self, proxy: Proxy) -> None:
        """Add proxy to pool.

        Args:
            proxy: Proxy to add
        """
        # Avoid duplicates
        if not any(p.address == proxy.address and p.port == proxy.port for p in self.proxies):
            self.proxies.append(proxy)
            logger.debug(f"Added proxy: {proxy.url_no_auth}")

    def remove(self, proxy: Proxy) -> None:
        """Remove proxy from pool.

        Args:
            proxy: Proxy to remove
        """
        self.proxies = [p for p in self.proxies if not (p.address == proxy.address and p.port == proxy.port)]

    def get_healthy(self) -> list[Proxy]:
        """Get all healthy proxies.

        Returns:
            List of healthy proxies
        """
        return [p for p in self.proxies if p.is_healthy]

    def get_by_address(self, address: str, port: int) -> Proxy | None:
        """Get proxy by address and port.

        Args:
            address: Proxy address
            port: Proxy port

        Returns:
            Proxy or None
        """
        for proxy in self.proxies:
            if proxy.address == address and proxy.port == port:
                return proxy
        return None

    @property
    def size(self) -> int:
        """Get pool size.

        Returns:
            Total number of proxies
        """
        return len(self.proxies)

    @property
    def healthy_count(self) -> int:
        """Get count of healthy proxies.

        Returns:
            Number of healthy proxies
        """
        return len(self.get_healthy())

    def clear(self) -> None:
        """Clear all proxies from pool."""
        self.proxies.clear()

    def to_list(self) -> list[dict[str, Any]]:
        """Convert to list of dictionaries.

        Returns:
            List of proxy dictionaries
        """
        return [p.to_dict() for p in self.proxies]


class ProxyManager:
    """Manages proxy pool with loading and persistence."""

    def __init__(self) -> None:
        """Initialize proxy manager."""
        self.pool = ProxyPool()
        self._enabled = settings.proxy_enabled

    @property
    def enabled(self) -> bool:
        """Check if proxy rotation is enabled.

        Returns:
            True if enabled
        """
        return self._enabled

    def enable(self) -> None:
        """Enable proxy rotation."""
        self._enabled = True
        logger.info("Proxy rotation enabled")

    def disable(self) -> None:
        """Disable proxy rotation."""
        self._enabled = False
        logger.info("Proxy rotation disabled")

    def load_from_file(self, filepath: str | Path | None = None) -> int:
        """Load proxies from file.

        Args:
            filepath: Path to proxy list file

        Returns:
            Number of proxies loaded
        """
        filepath = Path(filepath or settings.proxy_list_file)

        if not filepath.exists():
            logger.warning(f"Proxy file not found: {filepath}")
            return 0

        count = 0
        with open(filepath, "r") as f:
            for line in f:
                proxy = Proxy.from_string(line)
                if proxy:
                    self.pool.add(proxy)
                    count += 1

        logger.info(f"Loaded {count} proxies from {filepath}")
        return count

    def load_from_list(self, proxy_strings: list[str]) -> int:
        """Load proxies from list of strings.

        Args:
            proxy_strings: List of proxy strings

        Returns:
            Number of proxies loaded
        """
        count = 0
        for proxy_str in proxy_strings:
            proxy = Proxy.from_string(proxy_str)
            if proxy:
                self.pool.add(proxy)
                count += 1

        logger.info(f"Loaded {count} proxies from list")
        return count

    def add_proxy(
        self,
        address: str,
        port: int,
        protocol: str = "http",
        username: str | None = None,
        password: str | None = None,
        country: str | None = None,
    ) -> Proxy:
        """Add single proxy to pool.

        Args:
            address: Proxy IP address
            port: Proxy port
            protocol: Proxy protocol
            username: Auth username
            password: Auth password
            country: Country code

        Returns:
            Added proxy
        """
        proxy = Proxy(
            address=address,
            port=port,
            protocol=protocol,
            username=username,
            password=password,
            country=country,
        )
        self.pool.add(proxy)
        return proxy

    def remove_proxy(self, address: str, port: int) -> bool:
        """Remove proxy from pool.

        Args:
            address: Proxy address
            port: Proxy port

        Returns:
            True if removed
        """
        proxy = self.pool.get_by_address(address, port)
        if proxy:
            self.pool.remove(proxy)
            return True
        return False

    def mark_healthy(self, proxy: Proxy, response_time: float | None = None) -> None:
        """Mark proxy as healthy.

        Args:
            proxy: Proxy to mark
            response_time: Response time
        """
        proxy.is_healthy = True
        if response_time is not None:
            proxy.response_time = response_time

    def mark_unhealthy(self, proxy: Proxy) -> None:
        """Mark proxy as unhealthy.

        Args:
            proxy: Proxy to mark
        """
        proxy.is_healthy = False
        logger.warning(f"Proxy marked unhealthy: {proxy.url_no_auth}")

    def get_all(self) -> list[Proxy]:
        """Get all proxies.

        Returns:
            All proxies in pool
        """
        return self.pool.proxies

    def get_healthy(self) -> list[Proxy]:
        """Get healthy proxies.

        Returns:
            Healthy proxies
        """
        return self.pool.get_healthy()

    def get_stats(self) -> dict[str, Any]:
        """Get proxy pool statistics.

        Returns:
            Statistics dictionary
        """
        all_proxies = self.pool.proxies
        healthy = self.pool.get_healthy()

        total_requests = sum(p.total_requests for p in all_proxies)
        total_success = sum(p.success_count for p in all_proxies)

        avg_response_time = None
        proxies_with_time = [p for p in healthy if p.response_time is not None]
        if proxies_with_time:
            avg_response_time = sum(p.response_time for p in proxies_with_time) / len(proxies_with_time)

        return {
            "enabled": self._enabled,
            "total": self.pool.size,
            "healthy": self.pool.healthy_count,
            "unhealthy": self.pool.size - self.pool.healthy_count,
            "total_requests": total_requests,
            "success_rate": (total_success / total_requests * 100) if total_requests > 0 else 0,
            "avg_response_time": round(avg_response_time, 3) if avg_response_time else None,
        }

    def save_to_file(self, filepath: str | Path) -> None:
        """Save proxies to file.

        Args:
            filepath: Output file path
        """
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, "w") as f:
            for proxy in self.pool.proxies:
                if proxy.username and proxy.password:
                    f.write(f"{proxy.address}:{proxy.port}:{proxy.username}:{proxy.password}\n")
                else:
                    f.write(f"{proxy.address}:{proxy.port}\n")

        logger.info(f"Saved {self.pool.size} proxies to {filepath}")
