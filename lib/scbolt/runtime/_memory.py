"""Process-memory controls shared by long-running scBOLT stages."""

from __future__ import annotations

import argparse
import ctypes
import gc
import resource
import sys
from pathlib import Path


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
