"""
Lightweight circuit breaker for external API calls.

After `failure_threshold` consecutive failures, the circuit opens for `cooldown_seconds`
and returns None (caller should use cached/fallback data).
"""
import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """
    Simple circuit breaker: tracks consecutive failures per service.

    States:
        CLOSED  — normal operation, requests pass through
        OPEN    — too many failures, requests short-circuit for cooldown_seconds
    """

    def __init__(self, name: str, failure_threshold: int = 3, cooldown_seconds: float = 60.0):
        self.name = name
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self._consecutive_failures = 0
        self._open_until: Optional[float] = None

    @property
    def is_open(self) -> bool:
        """Check if circuit is open (blocking requests)."""
        if self._open_until is None:
            return False
        if time.monotonic() >= self._open_until:
            # Cooldown expired — half-open, allow next attempt
            self._open_until = None
            self._consecutive_failures = 0
            logger.info(f"[CircuitBreaker:{self.name}] Cooldown expired, circuit half-open")
            return False
        return True

    def record_success(self) -> None:
        """Record a successful call — reset failure counter."""
        if self._consecutive_failures > 0:
            logger.info(f"[CircuitBreaker:{self.name}] Success after {self._consecutive_failures} failures, resetting")
        self._consecutive_failures = 0
        self._open_until = None

    def record_failure(self) -> None:
        """Record a failed call — may open circuit."""
        self._consecutive_failures += 1
        if self._consecutive_failures >= self.failure_threshold:
            self._open_until = time.monotonic() + self.cooldown_seconds
            logger.warning(
                f"[CircuitBreaker:{self.name}] OPEN — {self._consecutive_failures} consecutive failures, "
                f"cooldown {self.cooldown_seconds}s"
            )


# Pre-configured circuit breakers for external services
open_meteo_breaker = CircuitBreaker("open-meteo", failure_threshold=3, cooldown_seconds=60)
floodhub_breaker = CircuitBreaker("floodhub", failure_threshold=3, cooldown_seconds=60)
fhi_weather_breaker = CircuitBreaker("fhi-weather", failure_threshold=3, cooldown_seconds=60)
