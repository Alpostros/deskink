import logging
from datetime import datetime

from PIL import Image

from .cache import Entry
from .pages import Canvas, Page
from .render import HEADER_H, H, W
from .render.chrome import age, blank, header
from .render.widgets import message

log = logging.getLogger(__name__)


def compose(page: Page, entry: Entry, now: datetime, index: int = 0, count: int = 1,
            wall: float | None = None) -> Image.Image:
    img, draw = blank()
    body = Canvas(img, draw, 0, HEADER_H + 1, W, H - HEADER_H - 1)

    stale = None
    if entry.error and entry.data is not None and entry.fetched_at is not None and wall is not None:
        stale = f"stale {age(wall - entry.fetched_at)}"

    status = None
    if entry.data is None:
        message(body, "no data yet" if not entry.error else "fetch failed", entry.error or "")
    else:
        try:
            page.render(entry.data, body)
            status = page.status(entry.data)
        except Exception as exc:
            log.exception("%s: render failed", page.title)
            img, draw = blank()
            body = Canvas(img, draw, 0, HEADER_H + 1, W, H - HEADER_H - 1)
            message(body, "render error", f"{type(exc).__name__}: {exc}")

    header(draw, page.title, now, index, count, status=status, stale=stale)
    return img


def notice(title: str, detail: str, now: datetime) -> Image.Image:
    img, draw = blank()
    message(Canvas(img, draw, 0, HEADER_H + 1, W, H - HEADER_H - 1), title, detail)
    header(draw, "deskink", now)
    return img
