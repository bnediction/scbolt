"""Solver deadlines and patience controls shared by inference scripts."""

import argparse
import re
import time
from threading import Lock

_DURATION_PATTERN = re.compile(
    r"^(?P<value>(?:\d+(?:\.\d*)?|\.\d+))(?P<unit>[smhd]?)$"
)
_DURATION_UNITS = {
    "": 1.0,
    "s": 1.0,
    "m": 60.0,
    "h": 3600.0,
    "d": 86400.0,
}

class SolverTimeout(TimeoutError):
    """Signal that the configured global solver deadline was reached."""


class SolverPatienceExpired(TimeoutError):
    """Signal that no solver improvement occurred within the patience."""


class SolverDeadline:
    """Track one monotonic deadline shared by successive solver views."""

    def __init__(self, timeout: float = 0.0) -> None:
        self._expires_at = time.monotonic() + timeout if timeout > 0 else None

    def remaining(self) -> float | None:
        """Return remaining seconds, or None when no deadline is configured."""

        if self._expires_at is None:
            return None
        return max(self._expires_at - time.monotonic(), 0.0)


class SolverPatience:
    """Track a resettable deadline since the latest solver improvement."""

    def __init__(self, patience: float = 0.0) -> None:
        self._duration = patience if patience > 0 else None
        self._lock = Lock()
        self._claimed = False
        self._expires_at = (
            time.monotonic() + patience if self._duration is not None else None
        )

    def reset(self) -> None:
        """Restart the patience after a solver objective improvement."""

        if self._duration is None:
            return
        with self._lock:
            if self._claimed:
                return
            self._expires_at = time.monotonic() + self._duration

    def ensure_remaining(self, duration: float) -> None:
        """Guarantee a minimum remaining delay without shortening patience."""

        if duration < 0:
            raise ValueError("remaining patience must be non-negative")
        if self._duration is None:
            return

        duration = min(duration, self._duration)
        with self._lock:
            if self._claimed:
                return
            minimum_expiry = time.monotonic() + duration
            if self._expires_at is None or self._expires_at < minimum_expiry:
                self._expires_at = minimum_expiry

    def remaining(self) -> float | None:
        """Return remaining seconds, or None when patience is disabled."""

        with self._lock:
            if self._expires_at is None:
                return None
            return max(self._expires_at - time.monotonic(), 0.0)

    def _claim_expiry(self) -> bool:
        """Atomically claim an elapsed patience unless it was just reset."""

        with self._lock:
            if self._expires_at is None or self._expires_at > time.monotonic():
                return False
            self._claimed = True
            return True


def parse_solver_timeout(value: str) -> float:
    """Parse a non-negative solver duration expressed in seconds to days."""

    match = _DURATION_PATTERN.fullmatch(value.strip())
    if match is None:
        raise argparse.ArgumentTypeError(
            "invalid timeout duration "
            f"(got {value!r}, expected a number followed by s, m, h or d)"
        )

    timeout = float(match.group("value"))
    return timeout * _DURATION_UNITS[match.group("unit")]


def format_duration(seconds: float) -> str:
    """Format a non-negative duration using compact day-to-second units."""

    if seconds < 0:
        raise ValueError("duration must be non-negative")
    if not float(seconds).is_integer():
        return f"{seconds:g}s"

    seconds = int(seconds)
    days, seconds = divmod(seconds, 24 * 60 * 60)
    hours, seconds = divmod(seconds, 60 * 60)
    minutes, seconds = divmod(seconds, 60)

    if days:
        if seconds:
            return f"{days}d{hours:02d}h{minutes:02d}m{seconds:02d}s"
        if minutes:
            return f"{days}d{hours:02d}h{minutes:02d}m"
        if hours:
            return f"{days}d{hours:02d}h"
        return f"{days}d"
    if hours:
        if seconds:
            return f"{hours}h{minutes:02d}m{seconds:02d}s"
        if minutes:
            return f"{hours}h{minutes:02d}m"
        return f"{hours}h"
    if minutes:
        if seconds:
            return f"{minutes}m{seconds:02d}s"
        return f"{minutes}m"
    return f"{seconds}s"
