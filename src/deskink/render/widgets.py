from PIL import ImageDraw

from . import BLACK
from .fonts import font


def width(draw: ImageDraw.ImageDraw, text: str, f) -> float:
    return draw.textlength(text, font=f)


def fit(draw, text: str, max_w: float, size: int, bold: bool = False, min_size: int = 9):
    while size > min_size and width(draw, text, font(size, bold)) > max_w:
        size -= 1
    return font(size, bold)


def ellipsize(draw, text: str, f, max_w: float) -> str:
    if width(draw, text, f) <= max_w:
        return text
    while text and width(draw, text + "…", f) > max_w:
        text = text[:-1]
    return text.rstrip() + "…"


def right(draw, x_right: float, y: float, text: str, f, fill=BLACK, anchor="rs"):
    draw.text((x_right, y), text, font=f, fill=fill, anchor=anchor)


def center(draw, box, text: str, f, fill=BLACK):
    x0, y0, x1, y1 = box
    draw.text(((x0 + x1) / 2, (y0 + y1) / 2), text, font=f, fill=fill, anchor="mm")


def dotted_rect(draw, box, step: int = 3, fill=BLACK):
    x0, y0, x1, y1 = box
    for x in range(x0, x1 + 1, step):
        draw.point((x, y0), fill=fill)
        draw.point((x, y1), fill=fill)
    for y in range(y0, y1 + 1, step):
        draw.point((x0, y), fill=fill)
        draw.point((x1, y), fill=fill)


def message(c, title: str, detail: str = ""):
    d = c.draw
    mid = c.y + c.h / 2
    d.text((c.x + c.w / 2, mid - (8 if detail else 0)), title, font=font(15, True), fill=BLACK, anchor="mm")
    if detail:
        f = font(11)
        d.text((c.x + c.w / 2, mid + 12), ellipsize(d, detail, f, c.w - 8), font=f, fill=BLACK, anchor="mm")
