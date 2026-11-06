from PIL import ImageDraw

from . import BLACK, WHITE

CLEAR, PARTLY, CLOUDY, FOG, DRIZZLE, RAIN, SNOW, THUNDER = (
    "clear", "partly", "cloudy", "fog", "drizzle", "rain", "snow", "thunder")


def kind(wmo: int) -> str:
    if wmo == 0:
        return CLEAR
    if wmo in (1, 2):
        return PARTLY
    if wmo == 3:
        return CLOUDY
    if wmo in (45, 48):
        return FOG
    if 51 <= wmo <= 57:
        return DRIZZLE
    if 61 <= wmo <= 67 or 80 <= wmo <= 82:
        return RAIN
    if 71 <= wmo <= 77 or wmo in (85, 86):
        return SNOW
    if wmo >= 95:
        return THUNDER
    return CLOUDY


def sun(d: ImageDraw.ImageDraw, cx: float, cy: float, r: float):
    w = max(1, round(r / 4))
    for i in range(8):
        dx, dy = [(1, 0), (0.7, 0.7), (0, 1), (-0.7, 0.7), (-1, 0), (-0.7, -0.7), (0, -1), (0.7, -0.7)][i]
        d.line((cx + dx * r * 1.35, cy + dy * r * 1.35, cx + dx * r * 1.85, cy + dy * r * 1.85),
               fill=BLACK, width=w)
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=BLACK, width=w, fill=WHITE)


def moon(d: ImageDraw.ImageDraw, cx: float, cy: float, r: float):
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=BLACK)
    o = r * 0.55
    d.ellipse((cx - r + o, cy - r - o * 0.4, cx + r + o, cy + r - o * 0.4), fill=WHITE)


def cloud(d: ImageDraw.ImageDraw, x: float, y: float, w: float, h: float):
    def shape(inset: float, fill):
        d.ellipse((x + inset, y + h * 0.35 + inset, x + w * 0.45 - inset, y + h - inset), fill=fill)
        d.ellipse((x + w * 0.2 + inset, y + inset, x + w * 0.75 - inset, y + h * 0.85 - inset), fill=fill)
        d.ellipse((x + w * 0.5 + inset, y + h * 0.25 + inset, x + w - inset, y + h - inset), fill=fill)
        d.rectangle((x + w * 0.22, y + h * 0.6 + inset, x + w * 0.78, y + h - inset), fill=fill)

    t = max(1.5, w / 14)
    shape(0, BLACK)
    shape(t, WHITE)


def draw(d: ImageDraw.ImageDraw, k: str, x: float, y: float, s: float, day: bool = True):
    if k == CLEAR:
        (sun if day else moon)(d, x + s / 2, y + s / 2, s * 0.24 if day else s * 0.32)
        return
    if k == PARTLY:
        (sun if day else moon)(d, x + s * 0.34, y + s * 0.32, s * 0.16 if day else s * 0.22)
        cloud(d, x + s * 0.2, y + s * 0.38, s * 0.8, s * 0.5)
        return
    if k == FOG:
        cloud(d, x + s * 0.12, y + s * 0.05, s * 0.76, s * 0.45)
        for i in range(3):
            yy = y + s * (0.62 + i * 0.13)
            d.line((x + s * 0.1 + (i % 2) * s * 0.08, yy, x + s * 0.9 - (i % 2) * s * 0.08, yy),
                   fill=BLACK, width=max(1, round(s / 16)))
        return

    top = k == CLOUDY
    cloud(d, x + s * 0.05, y + (s * 0.18 if top else s * 0.02), s * 0.9, s * (0.6 if top else 0.55))
    if top:
        return
    base = y + s * 0.64
    w = max(1, round(s / 16))
    if k in (RAIN, DRIZZLE):
        for i in range(3):
            xx = x + s * (0.28 + i * 0.22)
            if k == RAIN:
                d.line((xx, base, xx - s * 0.08, base + s * 0.28), fill=BLACK, width=w)
            else:
                for j in range(2):
                    r = max(1, s / 22)
                    cx, cy = xx - j * s * 0.05, base + s * (0.06 + j * 0.16)
                    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=BLACK)
    elif k == SNOW:
        for i in range(3):
            cx, cy, r = x + s * (0.28 + i * 0.22), base + s * (0.12 + (i % 2) * 0.12), s * 0.07
            d.line((cx - r, cy, cx + r, cy), fill=BLACK, width=w)
            d.line((cx, cy - r, cx, cy + r), fill=BLACK, width=w)
            d.line((cx - r * 0.7, cy - r * 0.7, cx + r * 0.7, cy + r * 0.7), fill=BLACK, width=w)
            d.line((cx - r * 0.7, cy + r * 0.7, cx + r * 0.7, cy - r * 0.7), fill=BLACK, width=w)
    elif k == THUNDER:
        cx = x + s * 0.5
        d.polygon([(cx + s * 0.06, base - s * 0.04), (cx - s * 0.12, base + s * 0.18), (cx, base + s * 0.18),
                   (cx - s * 0.08, base + s * 0.36), (cx + s * 0.14, base + s * 0.1), (cx + s * 0.02, base + s * 0.1)],
                  fill=BLACK)
