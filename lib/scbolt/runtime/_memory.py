"""Process-memory controls shared by long-running scBOLT stages."""

from __future__ import annotations

import ctypes
import gc
import sys


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
