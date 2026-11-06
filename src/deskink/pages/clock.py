from datetime import datetime

from ..render.fonts import font
from .base import Canvas, Page, register


@register("clock")
class ClockPage(Page):
    title = "Clock"
    refresh_every = 0

    def fetch(self) -> dict:
        return {}

    def sample(self) -> dict:
        return {"at": datetime(2026, 11, 6, 14, 32)}

    def render(self, data: dict, c: Canvas) -> None:
        data = data.get("at") or datetime.now()
        cx = c.x + c.w / 2
        c.draw.text((cx, c.y + c.h * 0.42), f"{data:%H:%M}", font=font(46, True), fill=0, anchor="mm")
        c.draw.text((cx, c.y + c.h * 0.85), f"{data:%A %-d %B}", font=font(13), fill=0, anchor="mm")
