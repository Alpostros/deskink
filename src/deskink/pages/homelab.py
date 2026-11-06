import json
import math
import socket
import urllib.error
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from ..config import ConfigError
from ..net import request
from ..render import BLACK, WHITE
from ..render.widgets import dotted_rect, ellipsize, fit
from .base import Canvas, Page, register

UP, DOWN, UNKNOWN = "up", "down", "unknown"
COLS, MAX_ROWS = 3, 6


class Unknown(Exception):
    pass


@dataclass
class Check:
    name: str
    url: str | None = None
    tcp: str | None = None
    prom: str | None = None
    contains: str | None = None
    insecure: bool = False
    timeout: float = 3.0

    @classmethod
    def from_options(cls, raw: dict, default_timeout: float) -> "Check":
        known = {"name", "url", "tcp", "prom", "contains", "insecure", "timeout"}
        if "name" not in raw:
            raise ConfigError("homelab: every check needs a name")
        if set(raw) - known:
            raise ConfigError(f"homelab check {raw['name']!r}: unknown key(s) {', '.join(sorted(set(raw) - known))}")
        kinds = [k for k in ("url", "tcp", "prom") if raw.get(k)]
        if len(kinds) != 1:
            raise ConfigError(f"homelab check {raw['name']!r}: needs exactly one of url, tcp, prom")
        return cls(**{"timeout": default_timeout, **raw})


def probe_http(check: Check) -> bool:
    try:
        status, body = request(check.url, timeout=check.timeout, insecure=check.insecure, limit=65536)
    except urllib.error.HTTPError:
        return False
    if status >= 400:
        return False
    return check.contains is None or check.contains in body.decode("utf-8", "replace")


def probe_tcp(check: Check) -> bool:
    host, _, port = check.tcp.rpartition(":")
    with socket.create_connection((host, int(port)), timeout=check.timeout):
        return True


def probe_prom(check: Check, prometheus: str | None) -> bool:
    if not prometheus:
        raise Unknown("no prometheus configured")
    url = f"{prometheus.rstrip('/')}/api/v1/query?{urllib.parse.urlencode({'query': check.prom})}"
    try:
        _, body = request(url, timeout=check.timeout)
        result = json.loads(body)["data"]["result"]
    except Exception as exc:
        raise Unknown(f"prometheus: {exc}") from exc
    return bool(result) and all(float(r["value"][1]) != 0 for r in result)


def probe(check: Check, prometheus: str | None = None) -> str:
    try:
        if check.prom:
            ok = probe_prom(check, prometheus)
        elif check.tcp:
            ok = probe_tcp(check)
        else:
            ok = probe_http(check)
    except Unknown:
        return UNKNOWN
    except (OSError, ValueError):
        ok = False
    return UP if ok else DOWN


@register("homelab")
class HomelabPage(Page):
    title = "Homelab"
    refresh_every = 45
    options_allowed = ("checks", "prometheus", "timeout", "fail_threshold", "workers")

    def __init__(self, options=None):
        super().__init__(options)
        timeout = float(self.opt("timeout", 3.0))
        self.checks = [Check.from_options(c, timeout) for c in self.opt("checks", required=True)]
        if not self.checks:
            raise ConfigError("homelab: no checks configured")
        if len(self.checks) > COLS * MAX_ROWS:
            raise ConfigError(f"homelab: at most {COLS * MAX_ROWS} checks per page; add a second homelab page")
        self.prometheus = self.opt("prometheus")
        self.threshold = int(self.opt("fail_threshold", 2))
        self.workers = int(self.opt("workers", 8))
        self.fails = {c.name: 0 for c in self.checks}
        self.state = {c.name: UNKNOWN for c in self.checks}

    def apply(self, results: dict[str, str]) -> list[dict]:
        for name, result in results.items():
            if result == DOWN:
                self.fails[name] += 1
                if self.fails[name] >= self.threshold:
                    self.state[name] = DOWN
            else:
                self.fails[name] = 0
                self.state[name] = result
        return [{"name": c.name, "state": self.state[c.name]} for c in self.checks]

    def fetch(self) -> list[dict]:
        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            states = pool.map(lambda c: probe(c, self.prometheus), self.checks)
            return self.apply(dict(zip([c.name for c in self.checks], states, strict=True)))

    def sample(self) -> list[dict]:
        out = [{"name": c.name, "state": UP} for c in self.checks]
        if len(out) > 4:
            out[4]["state"] = DOWN
        if len(out) > 7:
            out[7]["state"] = UNKNOWN
        return out

    def status(self, data: list[dict]) -> str:
        down = sum(r["state"] == DOWN for r in data)
        if down:
            return f"{down} DOWN"
        up = sum(r["state"] == UP for r in data)
        return f"{up}/{len(data)} up"

    def render(self, data: list[dict], c: Canvas) -> None:
        d = c.draw
        rows = max(1, math.ceil(len(data) / COLS))
        tile_w = (c.w - 4) / COLS
        tile_h = min(26, (c.h - 2) / rows)
        top = c.y + 1 + ((c.h - 2) - tile_h * rows) / 2
        size = 12 if tile_h >= 16 else 10
        for i, r in enumerate(data):
            col, row = i % COLS, i // COLS
            x0 = c.x + 2 + col * tile_w
            y0 = top + row * tile_h
            box = (round(x0 + 1), round(y0 + 1), round(x0 + tile_w - 2), round(y0 + tile_h - 2))
            label = r["name"]
            fg = BLACK
            if r["state"] == DOWN:
                d.rectangle(box, fill=BLACK)
                fg = WHITE
                label = label.upper()
            elif r["state"] == UNKNOWN:
                dotted_rect(d, box)
                label = f"{label}?"
            f = fit(d, label, tile_w - 8, size, bold=True, min_size=8)
            label = ellipsize(d, label, f, tile_w - 8)
            d.text((box[0] + 4, (box[1] + box[3]) / 2 + 1), label, font=f, fill=fg, anchor="lm")
