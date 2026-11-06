import logging
import time
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

log = logging.getLogger(__name__)


@dataclass
class Entry:
    data: Any = None
    fetched_at: float | None = None
    error: str | None = None


class Cache:
    def __init__(self, clock: Callable[[], float] = time.time):
        self.clock = clock
        self.entries: dict[int, Entry] = {}
        self.pending: dict[int, Future] = {}
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="fetch")

    def get(self, page) -> Entry:
        return self.entries.setdefault(id(page), Entry())

    def is_stale(self, page) -> bool:
        e = self.get(page)
        return e.fetched_at is None or self.clock() - e.fetched_at >= page.refresh_every

    def refresh(self, page) -> Entry:
        e = self.get(page)
        try:
            data = page.fetch()
        except Exception as exc:
            e.error = f"{type(exc).__name__}: {exc}"
            log.warning("%s: fetch failed: %s", page.title, e.error)
        else:
            e.data, e.fetched_at, e.error = data, self.clock(), None
        return e

    def prefetch(self, page) -> None:
        key = id(page)
        running = self.pending.get(key)
        if (running and not running.done()) or not self.is_stale(page):
            return
        self.pending[key] = self.pool.submit(self.refresh, page)

    def wait(self, page, timeout: float) -> None:
        running = self.pending.get(id(page))
        if running and not running.done():
            try:
                running.result(timeout=timeout)
            except Exception:
                log.warning("%s: fetch still running after %.0fs", page.title, timeout)

    def ensure(self, page, timeout: float) -> Entry:
        self.prefetch(page)
        if self.get(page).data is None:
            self.wait(page, timeout)
        return self.get(page)

    def close(self) -> None:
        self.pool.shutdown(wait=False, cancel_futures=True)
