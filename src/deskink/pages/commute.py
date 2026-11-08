import os
import urllib.parse
from collections import Counter
from datetime import datetime

from ..config import ConfigError
from ..net import get_json
from ..render import BLACK, WHITE
from ..render.fonts import font
from ..render.widgets import ellipsize, message, width
from .base import Canvas, Page, fixture, register

API = "https://api.tomtom.com/routing/1/calculateRoute"
KINDS = {"JAM": "JAM", "ROAD_WORK": "WORKS", "ROAD_CLOSURE": "CLOSED", "OTHER": "SLOW"}
SCRUB = {"latitude", "longitude", "points", "point", "instructionGroups", "street", "exitNumber",
         "signpostText", "roundaboutExitNumber", "message"}


def scrub(obj):
    if isinstance(obj, dict):
        return {k: scrub(v) for k, v in obj.items() if k not in SCRUB}
    if isinstance(obj, list):
        return [scrub(v) for v in obj]
    return obj


def _minutes(seconds) -> int:
    return round((seconds or 0) / 60)


def _road_at(instructions: list[dict], point_index: int) -> str:
    road = ""
    for ins in instructions:
        if ins.get("pointIndex", 0) > point_index:
            break
        if ins.get("roadNumbers"):
            road = ins["roadNumbers"][0]
    return road


def _main_road(instructions: list[dict], total_m: float) -> str:
    lengths: Counter = Counter()
    for here, nxt in zip(instructions, instructions[1:] + [{"routeOffsetInMeters": total_m}], strict=False):
        if here.get("roadNumbers"):
            lengths[here["roadNumbers"][0]] += nxt.get("routeOffsetInMeters", 0) - here.get("routeOffsetInMeters", 0)
    motorways = {r: m for r, m in lengths.items() if r[:1] in "AE"}
    pool = motorways or lengths
    return max(pool, key=pool.get) if pool else ""


def parse_route(route: dict) -> dict:
    s = route["summary"]
    instructions = route.get("guidance", {}).get("instructions", [])
    travel = s["travelTimeInSeconds"]
    free = s.get("noTrafficTravelTimeInSeconds", travel - s.get("trafficDelayInSeconds", 0))
    usual = s.get("historicTrafficTravelTimeInSeconds")
    incidents = []
    for sec in route.get("sections", []):
        if sec.get("sectionType") != "TRAFFIC":
            continue
        kind = sec.get("simpleCategory", "OTHER")
        incidents.append({
            "kind": KINDS.get(kind, "SLOW"),
            "road": _road_at(instructions, sec.get("startPointIndex", 0)),
            "delay": _minutes(sec.get("delayInSeconds")),
            "speed": sec.get("effectiveSpeedInKmh"),
            "closed": kind == "ROAD_CLOSURE",
        })
    incidents.sort(key=lambda i: (not i["closed"], -i["delay"]))
    arrival = s.get("arrivalTime")
    return {
        "minutes": _minutes(travel),
        "delay": max(0, _minutes(travel) - _minutes(free)),
        "free": _minutes(free),
        "usual": _minutes(usual) if usual else None,
        "arrive": datetime.fromisoformat(arrival).strftime("%H:%M") if arrival else "",
        "km": round(s.get("lengthInMeters", 0) / 1000, 1),
        "via": _main_road(instructions, s.get("lengthInMeters", 0)),
        "incidents": [i for i in incidents if i["delay"] >= 1 or i["closed"]],
    }


def parse(raw: dict) -> dict:
    routes = raw.get("routes") or []
    if not routes:
        raise ValueError("no route returned")
    best = parse_route(routes[0])
    best["alternative"] = parse_route(routes[1]) if len(routes) > 1 else None
    return best


def _point(value, key: str) -> tuple[float, float]:
    try:
        lat, lon = (float(v) for v in value)
    except (TypeError, ValueError):
        raise ConfigError(f"commute: {key} must be [latitude, longitude]") from None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ConfigError(f"commute: {key} is out of range")
    return lat, lon


@register("commute")
class CommutePage(Page):
    title = "Commute"
    refresh_every = 300
    options_allowed = ("origin", "destination", "alternatives", "alert_delay_min", "api_key_env", "api_url",
                       "travel_mode")

    def __init__(self, options=None):
        super().__init__(options)
        self.origin = _point(self.opt("origin", required=True), "origin")
        self.destination = _point(self.opt("destination", required=True), "destination")
        self.alternatives = int(self.opt("alternatives", 1))
        if not 0 <= self.alternatives <= 2:
            raise ConfigError("commute: alternatives must be 0, 1 or 2")
        if self.refresh_every < 60:
            raise ConfigError("commute: refresh_every below 60 s would burn through the free API quota")
        self.alert = float(self.opt("alert_delay_min", 10))
        self.key_env = str(self.opt("api_key_env", "TOMTOM_API_KEY"))
        self.api = str(self.opt("api_url", API))
        self.mode = str(self.opt("travel_mode", "car"))

    def url(self, key: str) -> str:
        where = ":".join(f"{lat:.6f},{lon:.6f}" for lat, lon in (self.origin, self.destination))
        q = [("key", key), ("traffic", "true"), ("departAt", "now"), ("travelMode", self.mode),
             ("routeType", "fastest"), ("computeTravelTimeFor", "all"), ("sectionType", "traffic"),
             ("instructionsType", "coded"), ("maxAlternatives", self.alternatives)]
        return f"{self.api}/{where}/json?{urllib.parse.urlencode(q)}"

    def fetch(self) -> dict:
        key = os.environ.get(self.key_env)
        if not key:
            raise RuntimeError(f"${self.key_env} is not set")
        return parse(get_json(self.url(key), timeout=15))

    def sample(self) -> dict:
        return parse(fixture("commute.json"))

    def status(self, data: dict) -> str | None:
        return f"+{data['delay']} min" if data["delay"] >= 1 else None

    def render(self, data: dict, c: Canvas) -> None:
        d = c.draw
        x0, y0 = c.x, c.y
        big, unit = font(34, True), font(14, True)
        num = str(data["minutes"])
        box_w = width(d, num, big) + width(d, " min", unit) + 10
        baseline = data["usual"] if data.get("usual") is not None else data["free"]
        alert = data["minutes"] - baseline >= self.alert
        fg = WHITE if alert else BLACK
        if alert:
            d.rectangle((x0 + 1, y0 + 2, x0 + box_w, y0 + 44), fill=BLACK)
        d.text((x0 + 5, y0 + 38), num, font=big, fill=fg, anchor="ls")
        d.text((x0 + 5 + width(d, num, big), y0 + 38), " min", font=unit, fill=fg, anchor="ls")

        rx = x0 + max(box_w + 10, 112)
        small = font(11)
        delay = f"+{data['delay']} min traffic" if data["delay"] >= 1 else "no traffic"
        d.text((rx, y0 + 15), delay, font=font(13, True), fill=BLACK, anchor="ls")
        d.text((rx, y0 + 29), f"arrive {data['arrive']}" if data["arrive"] else "", font=small, fill=BLACK,
               anchor="ls")
        via = f"via {data['via']} · " if data["via"] else ""
        usual = f"usual {data['usual']} min" if data.get("usual") is not None else f"empty {data['free']} min"
        d.text((rx, y0 + 43), f"{via}{usual}", font=small, fill=BLACK, anchor="ls")
        d.line((x0 + 2, y0 + 50, c.right - 2, y0 + 50), fill=BLACK)

        rows = []
        alt = data.get("alternative")
        n_inc = 3 - (1 if alt else 0)
        for inc in data["incidents"][:n_inc]:
            rows.append(("inc", inc))
        if not data["incidents"]:
            rows.append(("text", "no jams on the route"))
        if alt:
            alt_via = f" via {alt['via']}" if alt["via"] else ""
            rows.append(("text", f"alternative{alt_via}: {alt['minutes']} min"))

        row_h = (c.bottom - (y0 + 52)) / 3
        tag_f, road_f = font(10, True), font(12, True)
        for i, (kind, row) in enumerate(rows[:3]):
            top = y0 + 52 + i * row_h
            base = top + row_h / 2 + 4
            if kind == "text":
                d.text((x0 + 4, base), row, font=small, fill=BLACK, anchor="ls")
                continue
            tag_w = 46
            d.rectangle((x0 + 3, top + 2, x0 + 3 + tag_w, top + row_h - 2), fill=BLACK)
            d.text((x0 + 3 + tag_w / 2, base - 1), row["kind"], font=tag_f, fill=WHITE, anchor="ms")
            right = "closed" if row["closed"] else f"+{row['delay']} min"
            d.text((c.right - 4, base), right, font=road_f, fill=BLACK, anchor="rs")
            label = row["road"] or "on route"
            if row.get("speed") and not row["closed"]:
                label += f"  {row['speed']} km/h"
            max_w = c.right - 4 - width(d, right, road_f) - 8 - (x0 + tag_w + 10)
            d.text((x0 + tag_w + 10, base), ellipsize(d, label, road_f, max_w), font=road_f, fill=BLACK,
                   anchor="ls")
        if not rows:
            message(c, "no route")
