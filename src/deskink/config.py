import os
import tomllib
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from pathlib import Path

DEFAULT_PATHS = ("config.toml", "/etc/deskink/config.toml")
DRIVERS = ("waveshare", "png")


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class QuietHours:
    start: time
    end: time
    show: str = "blank"

    def active(self, now: datetime) -> bool:
        t = now.time()
        if self.start <= self.end:
            return self.start <= t < self.end
        return t >= self.start or t < self.end

    def seconds_left(self, now: datetime) -> float:
        end = now.replace(hour=self.end.hour, minute=self.end.minute, second=0, microsecond=0)
        if end <= now:
            end += timedelta(days=1)
        return (end - now).total_seconds()


@dataclass(frozen=True)
class PageSpec:
    type: str
    duration: float
    options: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Config:
    pages: list[PageSpec]
    default_duration: float = 30
    driver: str = "waveshare"
    flip: bool = False
    full_refresh_every: int = 20
    png_path: str = "screen.png"
    quiet_hours: QuietHours | None = None


def find_config(explicit: str | None = None) -> Path:
    candidates = [explicit] if explicit else [os.environ.get("DESKINK_CONFIG"), *DEFAULT_PATHS]
    for c in candidates:
        if c and Path(c).is_file():
            return Path(c)
    if explicit:
        raise ConfigError(f"config file not found: {explicit}")
    raise ConfigError("no config found (tried $DESKINK_CONFIG, " + ", ".join(DEFAULT_PATHS) + ")")


def load(path: str | Path) -> Config:
    try:
        raw = tomllib.loads(Path(path).read_text())
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"{path}: {e}") from e
    return parse(raw)


def _clock(value, key: str) -> time:
    try:
        return time.fromisoformat(str(value))
    except ValueError as e:
        raise ConfigError(f"{key}: expected HH:MM, got {value!r}") from e


def _positive(value, key: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float) or value <= 0:
        raise ConfigError(f"{key}: expected a positive number, got {value!r}")
    return value


def parse(raw: dict) -> Config:
    default_duration = _positive(raw.get("default_duration", 30), "default_duration")

    display = raw.get("display", {})
    driver = display.get("driver", "waveshare")
    if driver not in DRIVERS:
        raise ConfigError(f"display.driver: expected one of {DRIVERS}, got {driver!r}")
    full_every = display.get("full_refresh_every", 20)
    if isinstance(full_every, bool) or not isinstance(full_every, int) or full_every < 1:
        raise ConfigError(f"display.full_refresh_every: expected an integer >= 1, got {full_every!r}")

    quiet = None
    if "quiet_hours" in raw:
        q = raw["quiet_hours"]
        if "start" not in q or "end" not in q:
            raise ConfigError("quiet_hours: needs both start and end")
        quiet = QuietHours(_clock(q["start"], "quiet_hours.start"), _clock(q["end"], "quiet_hours.end"),
                           str(q.get("show", "blank")))
        if quiet.start == quiet.end:
            raise ConfigError("quiet_hours: start and end are the same")

    pages = []
    for i, p in enumerate(raw.get("pages", [])):
        if "type" not in p:
            raise ConfigError(f"pages[{i}]: missing type")
        if not p.get("enabled", True):
            continue
        options = {k: v for k, v in p.items() if k not in ("type", "duration", "enabled")}
        duration = _positive(p.get("duration", default_duration), f"pages[{i}].duration")
        pages.append(PageSpec(p["type"], duration, options))
    if not pages:
        raise ConfigError("no enabled [[pages]] in config")

    return Config(
        pages=pages,
        default_duration=default_duration,
        driver=driver,
        flip=bool(display.get("flip", False)),
        full_refresh_every=full_every,
        png_path=str(display.get("png_path", "screen.png")),
        quiet_hours=quiet,
    )
