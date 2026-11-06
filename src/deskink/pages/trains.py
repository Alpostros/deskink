import os
import urllib.parse
from datetime import datetime, timedelta

from ..config import ConfigError
from ..net import get_json
from ..render import BLACK, WHITE
from ..render.fonts import font
from ..render.widgets import ellipsize, message
from .base import Canvas, Page, fixture, register

API = "https://gateway.apiportal.ns.nl/reisinformatie-api/api/v2/departures"
ABBREVIATIONS = ((" Centraal", " C."), ("Schiphol Airport", "Schiphol"))


def ts(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S%z")


def abbreviate(name: str) -> str:
    for long, short in ABBREVIATIONS:
        name = name.replace(long, short)
    return name


def _matches(direction: str, names) -> bool:
    return any(n.casefold() in direction.casefold() for n in names)


def parse(raw: dict, now: datetime, rows: int = 4, min_minutes: float = 0,
          only=(), exclude=(), short: bool = True) -> list[dict]:
    out = []
    for d in raw.get("payload", {}).get("departures", []):
        planned = ts(d["plannedDateTime"])
        actual = ts(d.get("actualDateTime") or d["plannedDateTime"])
        if (actual - now).total_seconds() < min_minutes * 60:
            continue
        direction = d.get("direction", "?")
        if (only and not _matches(direction, only)) or (exclude and _matches(direction, exclude)):
            continue
        planned_track, actual_track = d.get("plannedTrack", ""), d.get("actualTrack")
        out.append({
            "time": f"{planned:%H:%M}",
            "delay": round((actual - planned).total_seconds() / 60),
            "category": d.get("trainCategory") or d.get("product", {}).get("categoryCode", ""),
            "direction": abbreviate(direction) if short else direction,
            "track": actual_track or planned_track,
            "track_changed": bool(actual_track) and actual_track != planned_track,
            "cancelled": bool(d.get("cancelled")),
        })
        if len(out) >= rows:
            break
    return out


@register("trains")
class TrainsPage(Page):
    title = "Trains"
    refresh_every = 60
    options_allowed = ("station", "rows", "min_minutes", "only_destinations", "exclude_destinations",
                       "abbreviate", "api_key_env", "api_url")

    def __init__(self, options=None):
        super().__init__(options)
        self.station = str(self.opt("station", required=True))
        self.rows = int(self.opt("rows", 4))
        if not 1 <= self.rows <= 6:
            raise ConfigError("trains: rows must be between 1 and 6")
        self.min_minutes = float(self.opt("min_minutes", 0))
        self.only = list(self.opt("only_destinations", []))
        self.exclude = list(self.opt("exclude_destinations", []))
        self.short = bool(self.opt("abbreviate", True))
        self.key_env = str(self.opt("api_key_env", "NS_API_KEY"))
        self.api = str(self.opt("api_url", API))

    def _parse(self, raw, now):
        return parse(raw, now, self.rows, self.min_minutes, self.only, self.exclude, self.short)

    def fetch(self) -> list[dict]:
        key = os.environ.get(self.key_env)
        if not key:
            raise RuntimeError(f"${self.key_env} is not set")
        url = f"{self.api}?{urllib.parse.urlencode({'station': self.station, 'maxJourneys': 20})}"
        raw = get_json(url, {"Ocp-Apim-Subscription-Key": key})
        return self._parse(raw, datetime.now().astimezone())

    def sample(self) -> list[dict]:
        raw = fixture("trains.json")
        first = ts(raw["payload"]["departures"][0]["plannedDateTime"])
        return self._parse(raw, first - timedelta(minutes=1))

    def render(self, data: list[dict], c: Canvas) -> None:
        if not data:
            message(c, "no departures", f"from {self.station}")
            return
        d = c.draw
        row_h = c.h / self.rows
        big, small, cat_f = font(14, True), font(11, True), font(10, True)
        track_r = c.right - 3
        for i, dep in enumerate(data):
            top = c.y + i * row_h
            base = top + row_h / 2 + 5
            mid = top + row_h / 2
            d.text((c.x + 3, base), dep["time"], font=big, fill=BLACK, anchor="ls")
            if dep["delay"] > 0:
                d.text((c.x + 51, base), f"+{dep['delay']}", font=small, fill=BLACK, anchor="ls")
            d.text((c.x + 75, base), dep["category"][:3], font=cat_f, fill=BLACK, anchor="ls")

            track_w = 22
            if dep["cancelled"]:
                box = (track_r - track_w, mid - 8, track_r, mid + 8)
                d.rectangle(box, fill=BLACK)
                d.line((box[0] + 6, box[1] + 4, box[2] - 6, box[3] - 4), fill=WHITE, width=2)
                d.line((box[0] + 6, box[3] - 4, box[2] - 6, box[1] + 4), fill=WHITE, width=2)
            elif dep["track"]:
                if dep["track_changed"]:
                    d.rectangle((track_r - track_w, mid - 9, track_r, mid + 9), fill=BLACK)
                d.text((track_r - track_w / 2, base), dep["track"], font=big,
                       fill=WHITE if dep["track_changed"] else BLACK, anchor="ms")

            x_dir = c.x + 101
            name = ellipsize(d, dep["direction"], big, track_r - track_w - 6 - x_dir)
            d.text((x_dir, base), name, font=big, fill=BLACK, anchor="ls")
            if dep["cancelled"]:
                d.line((c.x + 2, mid + 1, track_r - track_w - 4, mid + 1), fill=BLACK, width=2)
            if i < len(data) - 1:
                for x in range(c.x + 2, c.right - 2, 4):
                    d.point((x, int(top + row_h)), fill=BLACK)
