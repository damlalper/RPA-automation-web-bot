"""Proxy health checking."""

import asyncio
import time
from typing import TYPE_CHECKING

import httpx

from src.core.config import settings
from src.monitoring.logger import get_logger, log_proxy_event

if TYPE_CHECKING:
    from .manager import Proxy, ProxyManager

logger = get_logger(__name__)

# Test URLs for health checks
TEST_URLS = [
    "https://httpbin.org/ip",
    "https://api.ipify.org?format=json",
    "https://www.google.com",
]


class ProxyHealthChecker:
    """Health checker for proxy servers."""

    def __init__(
        self,
        manager: "ProxyManager",
        timeout: float | None = None,
        test_url: str | None = None,
    ) -> None:
        """Initialize health checker.

        Args:
            manager: ProxyManager instance
            timeout: Request timeout in seconds
            test_url: URL to test proxies against
        """
        self.manager = manager
        self.timeout = timeout or settings.proxy_timeout
        self.test_url = test_url or TEST_URLS[0]
        self._is_running = False

    async def check_proxy(self, proxy: "Proxy") -> bool:
        """Check if proxy is healthy.

        Args:
            proxy: Proxy to check

        Returns:
            True if proxy is healthy
        """
        start_time = time.time()

        try:
            async with httpx.AsyncClient(
                proxy=proxy.url,
                timeout=self.timeout,
                verify=False,
            ) as client:
                response = await client.get(self.test_url)
                response_time = time.time() - start_time

                if response.status_code == 200:
                    self.manager.mark_healthy(proxy, response_time)
                    log_proxy_event(
                        proxy=proxy.url_no_auth,
                        action="health_check",
                        success=True,
                        response_time=response_time,
                    )
                    return True

        except httpx.TimeoutException:
            logger.debug(f"Proxy timeout: {proxy.url_no_auth}")
        except httpx.ProxyError as e:
            logger.debug(f"Proxy error: {proxy.url_no_auth} | {e}")
        except Exception as e:
            logger.debug(f"Health check failed: {proxy.url_no_auth} | {e}")

        self.manager.mark_unhealthy(proxy)
        log_proxy_event(
            proxy=proxy.url_no_auth,
            action="health_check",
            success=False,
        )
        return False

    def check_proxy_sync(self, proxy: "Proxy") -> bool:
        """Synchronous proxy health check.

        Args:
            proxy: Proxy to check

        Returns:
            True if proxy is healthy
        """
        start_time = time.time()

        try:
            with httpx.Client(
                proxy=proxy.url,
                timeout=self.timeout,
                verify=False,
            ) as client:
                response = client.get(self.test_url)
                response_time = time.time() - start_time

                if response.status_code == 200:
                    self.manager.mark_healthy(proxy, response_time)
                    return True

        except Exception as e:
            logger.debug(f"Health check failed: {proxy.url_no_auth} | {e}")

        self.manager.mark_unhealthy(proxy)
        return False

    async def check_all(self, concurrency: int = 10) -> dict[str, int]:
        """Check all proxies in pool.

        Args:
            concurrency: Maximum concurrent checks

        Returns:
            Dictionary with healthy and unhealthy counts
        """
        proxies = self.manager.get_all()
        if not proxies:
            return {"healthy": 0, "unhealthy": 0, "total": 0}

        logger.info(f"Starting health check for {len(proxies)} proxies")

        semaphore = asyncio.Semaphore(concurrency)

        async def check_with_semaphore(proxy: "Proxy") -> bool:
            async with semaphore:
                return await self.check_proxy(proxy)

        results = await asyncio.gather(*[check_with_semaphore(p) for p in proxies])

        healthy = sum(1 for r in results if r)
        unhealthy = len(results) - healthy

        logger.info(f"Health check complete | healthy={healthy} | unhealthy={unhealthy}")

        return {
            "healthy": healthy,
            "unhealthy": unhealthy,
            "total": len(proxies),
        }

    def check_all_sync(self) -> dict[str, int]:
        """Synchronous check of all proxies.

        Returns:
            Dictionary with healthy and unhealthy counts
        """
        proxies = self.manager.get_all()
        healthy = 0
        unhealthy = 0

        for proxy in proxies:
            if self.check_proxy_sync(proxy):
                healthy += 1
            else:
                unhealthy += 1

        return {
            "healthy": healthy,
            "unhealthy": unhealthy,
            "total": len(proxies),
        }

    async def start_periodic_check(self, interval: int | None = None) -> None:
        """Start periodic health checking.

        Args:
            interval: Check interval in seconds
        """
        interval = interval or settings.proxy_health_check_interval
        self._is_running = True

        logger.info(f"Starting periodic health check | interval={interval}s")

        while self._is_running:
            try:
                await self.check_all()
            except Exception as e:
                logger.error(f"Periodic health check error: {e}")

            await asyncio.sleep(interval)

    def stop_periodic_check(self) -> None:
        """Stop periodic health checking."""
        self._is_running = False
        logger.info("Stopped periodic health check")

    async def verify_proxy_ip(self, proxy: "Proxy") -> str | None:
        """Verify proxy by checking external IP.

        Args:
            proxy: Proxy to verify

        Returns:
            External IP address or None
        """
        try:
            async with httpx.AsyncClient(
                proxy=proxy.url,
                timeout=self.timeout,
                verify=False,
            ) as client:
                response = await client.get("https://api.ipify.org?format=json")
                if response.status_code == 200:
                    data = response.json()
                    ip = data.get("ip")
                    logger.debug(f"Proxy {proxy.url_no_auth} external IP: {ip}")
                    return ip

        except Exception as e:
            logger.debug(f"IP verification failed: {proxy.url_no_auth} | {e}")

        return None

    async def benchmark_proxies(self, iterations: int = 3) -> list[dict]:
        """Benchmark all proxies with multiple iterations.

        Args:
            iterations: Number of test iterations per proxy

        Returns:
            List of benchmark results
        """
        proxies = self.manager.get_all()
        results = []

        for proxy in proxies:
            times = []
            successes = 0

            for _ in range(iterations):
                start = time.time()
                try:
                    async with httpx.AsyncClient(
                        proxy=proxy.url,
                        timeout=self.timeout,
                        verify=False,
                    ) as client:
                        response = await client.get(self.test_url)
                        if response.status_code == 200:
                            times.append(time.time() - start)
                            successes += 1
                except Exception:
                    pass

            avg_time = sum(times) / len(times) if times else None
            success_rate = (successes / iterations) * 100

            results.append({
                "proxy": proxy.url_no_auth,
                "avg_response_time": round(avg_time, 3) if avg_time else None,
                "success_rate": success_rate,
                "successful_requests": successes,
                "total_requests": iterations,
            })

        # Sort by success rate and response time
        results.sort(key=lambda x: (-x["success_rate"], x["avg_response_time"] or 999))

        return results
