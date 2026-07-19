"""Thread-pool controls shared by scBOLT scripts."""

from contextlib import contextmanager
from typing import Iterator


@contextmanager
def single_thread() -> Iterator[None]:
    """Limit supported numerical thread pools to one worker."""

    try:
        from threadpoolctl import threadpool_limits
    except ImportError:
        yield
    else:
        with threadpool_limits(limits=1):
            yield

