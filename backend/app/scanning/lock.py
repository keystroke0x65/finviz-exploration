"""One scan at a time per process.

Two overlapping scans double the Finviz load (each paced at 1 request/s, so the
manual one takes twice as long) and interleave their 'last scanned' writes.
"""

import threading
from collections.abc import Iterator
from contextlib import contextmanager

scan_lock = threading.Lock()


@contextmanager
def try_scan_lock() -> Iterator[bool]:
    """Yields whether the lock was acquired; never waits for it."""
    is_acquired = scan_lock.acquire(blocking=False)
    try:
        yield is_acquired
    finally:
        if is_acquired:
            scan_lock.release()
