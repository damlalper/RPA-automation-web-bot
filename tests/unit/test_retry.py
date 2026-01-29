"""Tests for retry logic."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock

from src.workers.retry import (
    RetryPolicy,
    RetryStrategy,
    RetryHandler,
    CircuitBreaker,
    retry,
)


class TestRetryPolicy:
    """Tests for RetryPolicy."""

    def test_fixed_delay(self):
        """Test fixed delay calculation."""
        policy = RetryPolicy(
            strategy=RetryStrategy.FIXED,
            initial_delay=1.0,
        )

        assert policy.calculate_delay(0) == 1.0
        assert policy.calculate_delay(1) == 1.0
        assert policy.calculate_delay(5) == 1.0

    def test_linear_delay(self):
        """Test linear delay calculation."""
        policy = RetryPolicy(
            strategy=RetryStrategy.LINEAR,
            initial_delay=1.0,
        )

        assert policy.calculate_delay(0) == 1.0
        assert policy.calculate_delay(1) == 2.0
        assert policy.calculate_delay(2) == 3.0

    def test_exponential_delay(self):
        """Test exponential delay calculation."""
        policy = RetryPolicy(
            strategy=RetryStrategy.EXPONENTIAL,
            initial_delay=1.0,
            multiplier=2.0,
        )

        assert policy.calculate_delay(0) == 1.0
        assert policy.calculate_delay(1) == 2.0
        assert policy.calculate_delay(2) == 4.0
        assert policy.calculate_delay(3) == 8.0

    def test_max_delay_cap(self):
        """Test max delay cap."""
        policy = RetryPolicy(
            strategy=RetryStrategy.EXPONENTIAL,
            initial_delay=1.0,
            multiplier=2.0,
            max_delay=5.0,
        )

        assert policy.calculate_delay(10) == 5.0

    def test_should_retry_default(self):
        """Test default retry behavior."""
        policy = RetryPolicy()

        assert policy.should_retry(Exception("test")) is True
        assert policy.should_retry(ValueError("test")) is True

    def test_non_retryable_exceptions(self):
        """Test non-retryable exceptions."""
        policy = RetryPolicy(
            non_retryable_exceptions=(ValueError, TypeError),
        )

        assert policy.should_retry(ValueError("test")) is False
        assert policy.should_retry(TypeError("test")) is False
        assert policy.should_retry(RuntimeError("test")) is True


class TestRetryHandler:
    """Tests for RetryHandler."""

    def test_successful_execution(self):
        """Test successful execution without retry."""
        handler = RetryHandler(RetryPolicy(max_retries=3))
        func = Mock(return_value="success")

        result = handler.execute_sync(func)

        assert result == "success"
        assert func.call_count == 1

    def test_retry_on_failure(self):
        """Test retry on failure."""
        handler = RetryHandler(RetryPolicy(max_retries=3, initial_delay=0.01))

        call_count = 0

        def failing_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("fail")
            return "success"

        result = handler.execute_sync(failing_func)

        assert result == "success"
        assert call_count == 3

    def test_max_retries_exceeded(self):
        """Test max retries exceeded."""
        handler = RetryHandler(RetryPolicy(max_retries=2, initial_delay=0.01))

        func = Mock(side_effect=Exception("always fail"))

        with pytest.raises(Exception, match="always fail"):
            handler.execute_sync(func)

        assert func.call_count == 3  # Initial + 2 retries

    def test_on_retry_callback(self):
        """Test on_retry callback."""
        handler = RetryHandler(RetryPolicy(max_retries=2, initial_delay=0.01))

        attempts = []

        def on_retry(attempt, error, delay):
            attempts.append(attempt)

        call_count = 0

        def failing_then_success():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("fail")
            return "success"

        handler.execute_sync(failing_then_success, on_retry=on_retry)

        assert len(attempts) == 1
        assert attempts[0] == 0

    @pytest.mark.asyncio
    async def test_async_execution(self):
        """Test async execution with retry."""
        handler = RetryHandler(RetryPolicy(max_retries=2, initial_delay=0.01))

        call_count = 0

        async def async_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("fail")
            return "success"

        result = await handler.execute_async(async_func)

        assert result == "success"
        assert call_count == 2


class TestRetryDecorator:
    """Tests for retry decorator."""

    def test_decorator_success(self):
        """Test decorator on successful function."""

        @retry(max_retries=3, initial_delay=0.01)
        def successful_func():
            return "success"

        result = successful_func()
        assert result == "success"

    def test_decorator_with_retry(self):
        """Test decorator with retry."""
        call_count = 0

        @retry(max_retries=3, initial_delay=0.01)
        def failing_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("fail")
            return "success"

        result = failing_func()

        assert result == "success"
        assert call_count == 2


class TestCircuitBreaker:
    """Tests for CircuitBreaker."""

    def test_initial_state_closed(self):
        """Test initial state is closed."""
        cb = CircuitBreaker()
        assert cb.state == CircuitBreaker.State.CLOSED

    def test_open_on_failures(self):
        """Test circuit opens after failures."""
        cb = CircuitBreaker(failure_threshold=3)

        for _ in range(3):
            cb.record_failure()

        assert cb.state == CircuitBreaker.State.OPEN

    def test_close_on_success(self):
        """Test circuit closes after successes in half-open."""
        cb = CircuitBreaker(failure_threshold=2, success_threshold=2, timeout=0.01)

        # Open the circuit
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitBreaker.State.OPEN

        # Wait for timeout to go to half-open
        import time
        time.sleep(0.02)
        assert cb.state == CircuitBreaker.State.HALF_OPEN

        # Record successes to close
        cb.record_success()
        cb.record_success()
        assert cb.state == CircuitBreaker.State.CLOSED

    def test_allow_request_when_closed(self):
        """Test requests allowed when closed."""
        cb = CircuitBreaker()
        assert cb.allow_request() is True

    def test_deny_request_when_open(self):
        """Test requests denied when open."""
        cb = CircuitBreaker(failure_threshold=1)
        cb.record_failure()

        assert cb.state == CircuitBreaker.State.OPEN
        assert cb.allow_request() is False

    def test_execute_success(self):
        """Test execute with successful function."""
        cb = CircuitBreaker()

        result = cb.execute(lambda: "success")

        assert result == "success"

    def test_execute_failure(self):
        """Test execute with failing function."""
        cb = CircuitBreaker()

        with pytest.raises(Exception):
            cb.execute(lambda: 1 / 0)

    def test_execute_when_open_raises(self):
        """Test execute raises when circuit is open."""
        cb = CircuitBreaker(failure_threshold=1)
        cb.record_failure()

        with pytest.raises(Exception, match="Circuit breaker is open"):
            cb.execute(lambda: "success")
