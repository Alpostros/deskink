import logging
import threading
import time
from collections.abc import Callable
from datetime import datetime

from PIL import Image

from .cache import Cache
from .config import Config
from .display import Display
from .frame import compose, notice
from .pages import Page
from .render.chrome import blank

log = logging.getLogger(__name__)


class RefreshPolicy:
    def __init__(self, every: int):
        self.every = max(1, every)
        self.k = 0
        self.force = True

    def next(self) -> bool:
        full = self.force or self.k % self.every == 0
        if full:
            self.force = False
            self.k = 0
        self.k += 1
        return full

    def force_full(self) -> None:
        self.force = True


class App:
    def __init__(self, cfg: Config, pages: list[Page], display: Display,
                 now: Callable[[], datetime] = datetime.now, wall: Callable[[], float] = time.time,
                 fetch_timeout: float = 15):
        self.cfg = cfg
        self.pages = pages
        self.display = display
        self.now = now
        self.wall = wall
        self.fetch_timeout = fetch_timeout
        self.cache = Cache(wall)
        self.policy = RefreshPolicy(cfg.full_refresh_every)
        self.stop = threading.Event()

    def wait(self, seconds: float) -> None:
        self.stop.wait(seconds)

    def frame(self, i: int) -> Image.Image:
        page = self.pages[i]
        return compose(page, self.cache.get(page), self.now(), i, len(self.pages), self.wall())

    def quiet_frame(self) -> Image.Image:
        show = self.cfg.quiet_hours.show
        for i, page in enumerate(self.pages):
            if show in (page.title, page.type):
                self.cache.ensure(page, self.fetch_timeout)
                return self.frame(i)
        return blank()[0]

    def run(self) -> None:
        i, quiet, n = 0, False, len(self.pages)
        log.info("rotating %d page(s): %s", n, ", ".join(f"{p.title} {p.duration:g}s" for p in self.pages))
        try:
            while not self.stop.is_set():
                now = self.now()
                qh = self.cfg.quiet_hours
                if qh and qh.active(now):
                    if not quiet:
                        log.info("quiet hours until %s", qh.end.strftime("%H:%M"))
                        self.display.show(self.quiet_frame(), full=True)
                        self.display.sleep()
                        quiet = True
                    self.wait(min(60.0, qh.seconds_left(now)))
                    continue
                if quiet:
                    log.info("quiet hours over")
                    quiet = False
                    self.policy.force_full()

                page = self.pages[i]
                self.cache.ensure(page, self.fetch_timeout)
                self.display.show(self.frame(i), full=self.policy.next())
                self.cache.prefetch(self.pages[(i + 1) % n])
                self.wait(page.duration)
                i = (i + 1) % n
        finally:
            self.shutdown()

    def shutdown(self) -> None:
        now = self.now()
        try:
            self.display.show(notice("stopped", f"at {now:%a %H:%M}", now), full=True)
        except Exception:
            log.exception("could not draw the stopped frame")
        finally:
            self.display.close()
            self.cache.close()
