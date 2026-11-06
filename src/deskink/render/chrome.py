from datetime import datetime

from PIL import Image, ImageDraw

from . import BLACK, HEADER_H, WHITE, H, W
from .fonts import font
from .widgets import ellipsize, width

DOT_R = 3
DOT_GAP = 9


def blank() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("1", (W, H), WHITE)
    return img, ImageDraw.Draw(img)


def header(draw: ImageDraw.ImageDraw, title: str, now: datetime, index: int = 0, count: int = 1,
           status: str | None = None, stale: str | None = None):
    small, bold = font(11), font(12, True)
    baseline = HEADER_H - 4

    x = W - 3
    clock = f"{now:%H:%M}"
    draw.text((x, baseline), clock, font=small, fill=BLACK, anchor="rs")
    x -= width(draw, clock, small) + 7

    if count > 1:
        cy = baseline - 4
        for i in reversed(range(count)):
            cx = x - DOT_R
            box = (cx - DOT_R, cy - DOT_R, cx + DOT_R, cy + DOT_R)
            draw.ellipse(box, fill=BLACK if i == index else WHITE, outline=BLACK)
            x -= DOT_GAP
        x -= 5

    for extra, f in ((stale, small), (status, bold)):
        if extra:
            draw.text((x, baseline), extra, font=f, fill=BLACK, anchor="rs")
            x -= width(draw, extra, f) + 6

    draw.text((3, baseline), ellipsize(draw, title, bold, x - 6), font=bold, fill=BLACK, anchor="ls")
    draw.line((0, HEADER_H, W, HEADER_H), fill=BLACK)


def age(seconds: float) -> str:
    if seconds < 90:
        return f"{int(seconds)}s"
    if seconds < 5400:
        return f"{round(seconds / 60)}m"
    return f"{round(seconds / 3600)}h"
