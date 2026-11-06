import math
import urllib.parse

from ..net import get_json
from ..render import BLACK
from ..render import icons as ic
from ..render.fonts import font
from ..render.widgets import fit
from .base import Canvas, Page, fixture, register

API = "https://api.open-meteo.com/v1/forecast"
BEAUFORT = (1, 6, 12, 20, 29, 39, 50, 62, 75, 89, 103, 118)
COMPASS = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")
SLOTS = 12


def beaufort(kmh: float) -> int:
    return sum(kmh >= limit for limit in BEAUFORT)


def compass(degrees: float) -> str:
    return COMPASS[round(degrees / 45) % 8]


def parse(raw: dict) -> dict:
    cur = raw["current"]
    hourly = raw["hourly"]
    hours = []
    for i, t in enumerate(hourly["time"]):
        if t > cur["time"] and len(hours) < 3:
            hours.append({
                "time": t[11:16],
                "temp": hourly["temperature_2m"][i],
                "kind": ic.kind(hourly["weather_code"][i]),
                "day": bool(hourly.get("is_day", [1] * len(hourly["time"]))[i]),
                "pop": hourly.get("precipitation_probability", [None] * len(hourly["time"]))[i],
            })
    m15 = raw.get("minutely_15", {})
    return {
        "temp": cur["temperature_2m"],
        "feels": cur.get("apparent_temperature"),
        "kind": ic.kind(cur["weather_code"]),
        "day": bool(cur.get("is_day", 1)),
        "wind_bft": beaufort(cur.get("wind_speed_10m", 0)),
        "wind_dir": compass(cur.get("wind_direction_10m", 0)),
        "hours": hours,
        "rain": [p or 0.0 for p in m15.get("precipitation", [])][:SLOTS],
        "rain_times": [t[11:16] for t in m15.get("time", [])][:SLOTS],
    }


def deg(value) -> str:
    return "–" if value is None else f"{round(value)}°"


@register("weather")
class WeatherPage(Page):
    title = "Weather"
    refresh_every = 600
    options_allowed = ("latitude", "longitude", "timezone", "rain_full_scale")

    def __init__(self, options=None):
        super().__init__(options)
        self.lat = float(self.opt("latitude", 52.0116))
        self.lon = float(self.opt("longitude", 4.3571))
        self.tz = str(self.opt("timezone", "Europe/Amsterdam"))
        self.full_scale = float(self.opt("rain_full_scale", 2.0))

    def url(self) -> str:
        q = {
            "latitude": self.lat, "longitude": self.lon, "timezone": self.tz,
            "current": "temperature_2m,apparent_temperature,weather_code,wind_speed_10m,wind_direction_10m,is_day",
            "hourly": "temperature_2m,weather_code,precipitation_probability,is_day",
            "minutely_15": "precipitation",
            "forecast_hours": 4, "forecast_minutely_15": SLOTS,
        }
        return f"{API}?{urllib.parse.urlencode(q)}"

    def fetch(self) -> dict:
        return parse(get_json(self.url()))

    def sample(self) -> dict:
        return parse(fixture("weather.json"))

    def render(self, data: dict, c: Canvas) -> None:
        d = c.draw
        x0, y0 = c.x, c.y
        ic.draw(d, data["kind"], x0 + 3, y0 + 4, 38, data["day"])
        temp = deg(data["temp"])
        d.text((x0 + 46, y0 + 34), temp, font=fit(d, temp, 54, 30, True), fill=BLACK, anchor="ls")
        small = font(11)
        d.text((x0 + 4, y0 + 56), f"feels {deg(data['feels'])}", font=small, fill=BLACK, anchor="ls")
        d.text((x0 + 4, y0 + 70), f"{data['wind_dir']} {data['wind_bft']} Bft", font=small, fill=BLACK,
               anchor="ls")

        split = x0 + 103
        strip_top = y0 + 76
        d.line((split, y0 + 3, split, strip_top - 4), fill=BLACK)
        col_w = (c.right - split - 2) / 3
        for i, h in enumerate(data["hours"]):
            cx = split + 2 + col_w * (i + 0.5)
            d.text((cx, y0 + 12), h["time"], font=font(11, True), fill=BLACK, anchor="ms")
            ic.draw(d, h["kind"], cx - 12, y0 + 15, 24, h["day"])
            d.text((cx, y0 + 54), deg(h["temp"]), font=font(13, True), fill=BLACK, anchor="ms")
            if h["pop"] is not None:
                d.text((cx, y0 + 68), f"{h['pop']}%", font=font(10), fill=BLACK, anchor="ms")

        self._rain(c, strip_top, data["rain"], data["rain_times"])

    def _rain(self, c: Canvas, top: float, rain: list[float], times: list[str]) -> None:
        d = c.draw
        base = c.bottom - 11
        left, right = c.x + 3, c.right - 3
        d.line((left, base, right, base), fill=BLACK)
        if not rain:
            return
        slot = (right - left) / SLOTS
        tick = font(9)
        if not any(r >= 0.05 for r in rain):
            d.text(((left + right) / 2, base - 3), "dry for the next 3 h", font=font(11, True), fill=BLACK,
                   anchor="ms")
        max_h = base - top - 1
        for i, mm in enumerate(rain):
            bx = left + i * slot
            if mm >= 0.05:
                h = max(2, round(max_h * min(1.0, math.sqrt(mm / self.full_scale))))
                d.rectangle((bx + 2, base - h, bx + slot - 2, base), fill=BLACK)
            if i % 4 == 0:
                d.line((bx, base, bx, base + 2), fill=BLACK)
                if i < len(times):
                    d.text((bx, base + 10), times[i], font=tick, fill=BLACK, anchor="ls")
