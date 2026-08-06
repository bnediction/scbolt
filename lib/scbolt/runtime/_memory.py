"""Process-memory controls shared by long-running scBOLT stages."""

from __future__ import annotations

import argparse
import ctypes
import gc
import resource
import sys
from dataclasses import dataclass
from pathlib import Path
from threading import Event, Lock, Thread
from typing import Any


SOLVER_MEMORY_PROBE_SECONDS = 1.0
SOLVER_MEMORY_PROJECTION_STEPS = 2


@dataclass(frozen=True)
class SolverMemoryPressure:
    """Describe one projected solver-memory budget crossing."""

    rss: int
    projected_rss: int
    limit: int


class SolverMemorySupervisor:
    """Monitor solver RSS and coordinate optional progress refreshes."""

    probe_seconds = SOLVER_MEMORY_PROBE_SECONDS
    projection_steps = SOLVER_MEMORY_PROJECTION_STEPS

    def __init__(self, memory_limit: int) -> None:
        if memory_limit <= 0:
            raise ValueError("solver memory limit must be positive")
        self.memory_limit = memory_limit
        self._finished = Event()
        self._lock = Lock()
        self._pressure: SolverMemoryPressure | None = None
        self._previous_rss: int | None = None
        self._progress = None
        self._thread: Thread | None = None
        self._view = None

    def start(self, view: Any) -> None:
        """Start supervising one solver view."""

        if self._thread is not None:
            raise RuntimeError("solver memory supervisor is already running")
        self._view = view
        self._previous_rss = current_rss_bytes()
        self._thread = Thread(
            target=self._watch,
            name="scbolt-solver-memory",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        """Stop monitoring and detach the supervised solver view."""

        self._finished.set()
        if self._thread is not None:
            self._thread.join()
            self._thread = None
        self._view = None

    def attach_progress(self, progress: Any) -> None:
        """Register a terminal progress display for the shared heartbeat."""

        with self._lock:
            self._progress = progress

    def detach_progress(self, progress: Any) -> None:
        """Detach a progress display if it is still registered."""

        with self._lock:
            if self._progress is progress:
                self._progress = None

    def memory_pressure(self) -> SolverMemoryPressure | None:
        """Return the first projected budget crossing, when observed."""

        with self._lock:
            return self._pressure

    def _watch(self) -> None:
        """Sample RSS and refresh the attached progress display."""

        while not self._finished.wait(self.probe_seconds):
            rss = current_rss_bytes()
            pressure = self._observe_rss(rss)
            progress = self._attached_progress()

            if progress is not None:
                try:
                    progress.refresh()
                except (OSError, RuntimeError, ValueError):
                    self.detach_progress(progress)

            if pressure is not None:
                self._interrupt_view()

    def _observe_rss(self, rss: int | None) -> SolverMemoryPressure | None:
        """Update memory growth and claim the first projected crossing."""

        if rss is None:
            return None

        previous_rss = self._previous_rss
        self._previous_rss = rss
        growth = max(0, rss - previous_rss) if previous_rss is not None else 0
        projected_rss = rss + self.projection_steps * growth

        with self._lock:
            if self._pressure is None and projected_rss >= self.memory_limit:
                self._pressure = SolverMemoryPressure(
                    rss=rss,
                    projected_rss=projected_rss,
                    limit=self.memory_limit,
                )
            return self._pressure

    def _attached_progress(self) -> Any:
        """Return the currently attached progress display."""

        with self._lock:
            return self._progress

    def _interrupt_view(self) -> None:
        """Request interruption until the solver acknowledges pressure."""

        view = self._view
        if view is None:
            return

        # Import lazily to keep the low-level memory module acyclic.
        from ._solver import interrupt_solver_view

        interrupt_solver_view(view, cancel_handler=False)


def parse_memory_limit(value: str) -> int | None:
    """Parse a memory size and return bytes."""

    value = value.strip()
    if not value:
        return None

    units = {
        "kb": 1000,
        "mb": 1000**2,
        "gb": 1000**3,
        "tb": 1000**4,
        "kib": 1024,
        "mib": 1024**2,
        "gib": 1024**3,
        "tib": 1024**4,
    }
    if value.isdigit():
        return int(value) * units["gb"]

    for unit, multiplier in units.items():
        if value.lower().endswith(unit):
            number = value[: -len(unit)]
            try:
                size = float(number)
            except ValueError as error:
                raise argparse.ArgumentTypeError(
                    f"expected positive memory size but received {value}"
                ) from error
            if size <= 0:
                raise argparse.ArgumentTypeError(
                    f"expected positive memory size but received {value}"
                )
            return int(size * multiplier)

    raise argparse.ArgumentTypeError(
        "expected positive memory size; integers are interpreted as GB"
    )


def current_rss_bytes() -> int | None:
    """Return resident memory using a current or conservative platform value."""

    status = Path("/proc/self/status")
    if status.exists():
        for line in status.read_text().splitlines():
            if line.startswith("VmRSS:"):
                fields = line.split()
                if len(fields) >= 2 and fields[1].isdigit():
                    return int(fields[1]) * 1024

    # macOS exposes peak rather than current RSS through the standard library.
    # This is deliberately conservative: after pressure is observed, queued
    # candidates continue one at a time instead of assuming memory was freed.
    usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if usage <= 0:
        return None
    if sys.platform == "darwin":
        return int(usage)
    return int(usage) * 1024


def format_memory_size(size: int | None) -> str:
    """Format memory bytes for logs."""

    if size is None:
        return "unknown"
    for unit, divisor in (("TB", 1000**4), ("GB", 1000**3), ("MB", 1000**2)):
        if size >= divisor:
            return f"{size / divisor:.1f}{unit}"
    return f"{size}B"


def release_unused_memory() -> bool:
    """Collect unreachable objects and return free glibc arenas to Linux."""

    gc.collect()
    if not sys.platform.startswith("linux"):
        return False

    try:
        malloc_trim = ctypes.CDLL(None).malloc_trim
    except (AttributeError, OSError):
        return False

    malloc_trim.argtypes = [ctypes.c_size_t]
    malloc_trim.restype = ctypes.c_int
    return bool(malloc_trim(0))
