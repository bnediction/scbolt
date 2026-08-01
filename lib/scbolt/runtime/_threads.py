"""Thread-pool controls shared by scBOLT scripts."""

from collections.abc import Generator
from contextlib import contextmanager


def get_clingo_parallel_mode(value: str) -> tuple[int | None, str | None]:
    """Translate a Clingo parallel mode for Python or command-line usage."""

    if "," in value:
        return None, f"--parallel-mode={value}"
    return int(value), None


def get_subset_minimal_clingo_settings(value: str) -> dict[str, object]:
    """Return parallel Clingo settings for subset-minimal enumeration."""

    parallel_jobs, parallel_option = get_clingo_parallel_mode(value)

    if parallel_option:
        return {"parallel": None, "clingo_options": [parallel_option]}
    if parallel_jobs <= 1:
        return {}

    return {"parallel": min(parallel_jobs, 14)}


@contextmanager
def single_thread() -> Generator[None, None, None]:
    """Limit supported numerical thread pools to one worker."""

    try:
        from threadpoolctl import threadpool_limits
    except ImportError:
        yield
    else:
        with threadpool_limits(limits=1):
            yield
