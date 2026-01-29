"""Retry logic and policies."""

import asyncio
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, TypeVar

from src.monitoring.logger import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class RetryStrategy(str, Enum):
    """Retry strategy types."""

    FIXED = "fixed"
    LINEAR = "linear"
    EXPONENTIAL = "exponential"
    EXPONENTIAL_JITTER = "exponential_jitter"


@dataclass
class RetryPolicy:
    """Configuration for retry behavior."""

    max_retries: int = 3
    initial_delay: float = 1.0
    max_delay: float = 60.0
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_JITTER
    multiplier: float = 2.0
    jitter_range: tuple[float, float] = (0.5, 1.5)

    # Exceptions to retry
    retryable_exceptions: tuple[type[Exception], ...] = (Exception,)
    # Exceptions to NOT retry
    non_retryable_exceptions: tuple[type[Exception], ...] = ()

    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt.

        Args:
            attempt: Current attempt number (0-indexed)

        Returns:
            Delay in seconds
        """
        if self.strategy == RetryStrategy.FIXED:
            delay = self.initial_delay

        elif self.strategy == RetryStrategy.LINEAR:
            delay = self.initial_delay * (attempt + 1)

        elif self.strategy == RetryStrategy.EXPONENTIAL:
            delay = self.initial_delay * (self.multiplier ** attempt)

        elif self.strategy == RetryStrategy.EXPONENTIAL_JITTER:
            base_delay = self.initial_delay * (self.multiplier ** attempt)
            jitter = random.uniform(*self.jitter_range)
            delay = base_delay * jitter

        else:
            delay = self.initial_delay

        return min(delay, self.max_delay)

    def should_retry(self, exception: Exception) -> bool:
        """Check if exception should trigger retry.

        Args:
            exception: Exception to check

        Returns:
            True if should retry
        """
        # Check non-retryable first
        if isinstance(exception, self.non_retryable_exceptions):
            return False

        # Then check retryable
        return isinstance(exception, self.retryable_exceptions)


@dataclass
class RetryState:
    """State of retry operation."""

    attempt: int = 0
    total_delay: float = 0.0
    errors: list[str] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)

    @property
    def elapsed_time(self) -> float:
        """Get total elapsed time.

        Returns:
            Elapsed time in seconds
        """
        return time.time() - self.start_time

    def record_error(self, error: Exception) -> None:
        """Record an error.

        Args:
            error: Exception that occurred
        """
        self.errors.append(f"Attempt {self.attempt}: {type(error).__name__}: {error}")


class RetryHandler:
    """Handles retry logic for operations."""

    def __init__(self, policy: RetryPolicy | None = None) -> None:
        """Initialize retry handler.

        Args:
            policy: Retry policy to use
        """
        self.policy = policy or RetryPolicy()

    def execute_sync(
        self,
        func: Callable[..., T],
        *args,
        on_retry: Callable[[int, Exception, float], None] | None = None,
        **kwargs,
    ) -> T:
        """Execute function with retry (synchronous).

        Args:
            func: Function to execute
            *args: Function arguments
            on_retry: Callback on retry (attempt, error, delay)
            **kwargs: Function keyword arguments

        Returns:
            Function result

        Raises:
            Last exception if all retries fail
        """
        state = RetryState()
        last_exception: Exception | None = None

        while state.attempt <= self.policy.max_retries:
            try:
                return func(*args, **kwargs)

            except Exception as e:
                last_exception = e
                state.record_error(e)

                if not self.policy.should_retry(e):
                    logger.warning(f"Non-retryable exception: {e}")
                    raise

                if state.attempt >= self.policy.max_retries:
                    logger.error(f"Max retries ({self.policy.max_retries}) exceeded")
                    raise

                delay = self.policy.calculate_delay(state.attempt)
                state.total_delay += delay

                logger.warning(
                    f"Retry {state.attempt + 1}/{self.policy.max_retries} | "
                    f"error={type(e).__name__} | delay={delay:.2f}s"
                )

                if on_retry:
                    on_retry(state.attempt, e, delay)

                time.sleep(delay)
                state.attempt += 1

        # Should not reach here, but just in case
        if last_exception:
            raise last_exception
        raise RuntimeError("Unexpected retry handler state")

    async def execute_async(
        self,
        func: Callable[..., T],
        *args,
        on_retry: Callable[[int, Exception, float], None] | None = None,
        **kwargs,
    ) -> T:
        """Execute async function with retry.

        Args:
            func: Async function to execute
            *args: Function arguments
            on_retry: Callback on retry
            **kwargs: Function keyword arguments

        Returns:
            Function result

        Raises:
            Last exception if all retries fail
        """
        state = RetryState()
        last_exception: Exception | None = None

        while state.attempt <= self.policy.max_retries:
            try:
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                return func(*args, **kwargs)

            except Exception as e:
                last_exception = e
                state.record_error(e)

                if not self.policy.should_retry(e):
                    logger.warning(f"Non-retryable exception: {e}")
                    raise

                if state.attempt >= self.policy.max_retries:
                    logger.error(f"Max retries ({self.policy.max_retries}) exceeded")
                    raise

                delay = self.policy.calculate_delay(state.attempt)
                state.total_delay += delay

                logger.warning(
                    f"Retry {state.attempt + 1}/{self.policy.max_retries} | "
                    f"error={type(e).__name__} | delay={delay:.2f}s"
                )

                if on_retry:
                    on_retry(state.attempt, e, delay)

                await asyncio.sleep(delay)
                state.attempt += 1

        if last_exception:
            raise last_exception
        raise RuntimeError("Unexpected retry handler state")

    def __call__(self, func: Callable[..., T]) -> Callable[..., T]:
        """Decorator for adding retry logic to function.

        Args:
            func: Function to decorate

        Returns:
            Decorated function
        """
        if asyncio.iscoroutinefunction(func):
            async def async_wrapper(*args, **kwargs):
                return await self.execute_async(func, *args, **kwargs)
            return async_wrapper
        else:
            def sync_wrapper(*args, **kwargs):
                return self.execute_sync(func, *args, **kwargs)
            return sync_wrapper


def retry(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_JITTER,
    **policy_kwargs,
) -> Callable:
    """Decorator factory for retry logic.

    Args:
        max_retries: Maximum retry attempts
        initial_delay: Initial delay in seconds
        strategy: Retry strategy
        **policy_kwargs: Additional policy arguments

    Returns:
        Decorator function
    """
    policy = RetryPolicy(
        max_retries=max_retries,
        initial_delay=initial_delay,
        strategy=strategy,
        **policy_kwargs,
    )
    handler = RetryHandler(policy)
    return handler


class CircuitBreaker:
    """Circuit breaker pattern for failure handling."""

    class State(str, Enum):
        CLOSED = "closed"  # Normal operation
        OPEN = "open"  # Failing, reject requests
        HALF_OPEN = "half_open"  # Testing recovery

    def __init__(
        self,
        failure_threshold: int = 5,
        success_threshold: int = 2,
        timeout: float = 60.0,
    ) -> None:
        """Initialize circuit breaker.

        Args:
            failure_threshold: Failures before opening
            success_threshold: Successes to close from half-open
            timeout: Time before half-open from open
        """
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.timeout = timeout

        self._state = self.State.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: float | None = None

    @property
    def state(self) -> State:
        """Get current state, checking for timeout.

        Returns:
            Current circuit breaker state
        """
        if self._state == self.State.OPEN:
            if self._last_failure_time and (time.time() - self._last_failure_time) > self.timeout:
                self._state = self.State.HALF_OPEN
                self._success_count = 0
        return self._state

    def record_success(self) -> None:
        """Record successful operation."""
        if self.state == self.State.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self.success_threshold:
                self._close()
        elif self.state == self.State.CLOSED:
            self._failure_count = 0

    def record_failure(self) -> None:
        """Record failed operation."""
        self._failure_count += 1
        self._last_failure_time = time.time()

        if self.state == self.State.HALF_OPEN:
            self._open()
        elif self._failure_count >= self.failure_threshold:
            self._open()

    def _open(self) -> None:
        """Open the circuit."""
        self._state = self.State.OPEN
        logger.warning("Circuit breaker opened")

    def _close(self) -> None:
        """Close the circuit."""
        self._state = self.State.CLOSED
        self._failure_count = 0
        logger.info("Circuit breaker closed")

    def allow_request(self) -> bool:
        """Check if request is allowed.

        Returns:
            True if request is allowed
        """
        return self.state != self.State.OPEN

    def execute(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Execute function through circuit breaker.

        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result

        Raises:
            Exception if circuit is open or function fails
        """
        if not self.allow_request():
            raise Exception("Circuit breaker is open")

        try:
            result = func(*args, **kwargs)
            self.record_success()
            return result
        except Exception as e:
            self.record_failure()
            raise
