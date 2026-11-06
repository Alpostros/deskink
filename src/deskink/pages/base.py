import json
from dataclasses import dataclass
from importlib import resources
from typing import Any, ClassVar

from PIL import Image, ImageDraw

from ..config import ConfigError, PageSpec

REGISTRY: dict[str, type["Page"]] = {}


def register(name: str):
    def wrap(cls):
        if name in REGISTRY:
            raise ValueError(f"page type {name!r} registered twice")
        cls.type = name
        REGISTRY[name] = cls
        return cls
    return wrap


@dataclass
class Canvas:
    img: Image.Image
    draw: ImageDraw.ImageDraw
    x: int
    y: int
    w: int
    h: int

    @property
    def right(self) -> int:
        return self.x + self.w

    @property
    def bottom(self) -> int:
        return self.y + self.h


class Page:
    type: ClassVar[str] = ""
    title: str = ""
    refresh_every: float = 60
    duration: float = 30
    options_allowed: ClassVar[tuple[str, ...]] = ()

    def __init__(self, options: dict | None = None):
        self.options = dict(options or {})
        unknown = set(self.options) - {"title", "refresh_every", *self.options_allowed}
        if unknown:
            raise ConfigError(f"{self.type}: unknown option(s) {', '.join(sorted(unknown))}")
        self.title = str(self.options.get("title", self.title or self.type))
        self.refresh_every = float(self.options.get("refresh_every", self.refresh_every))

    def opt(self, key: str, default: Any = None, required: bool = False) -> Any:
        if required and key not in self.options:
            raise ConfigError(f"{self.type}: missing required option {key!r}")
        return self.options.get(key, default)

    def fetch(self) -> Any:
        raise NotImplementedError

    def sample(self) -> Any:
        return None

    def render(self, data: Any, c: Canvas) -> None:
        raise NotImplementedError

    def status(self, data: Any) -> str | None:
        return None


def fixture(name: str) -> Any:
    return json.loads(resources.files("deskink.fixtures").joinpath(name).read_text())


def build(spec: PageSpec) -> Page:
    from . import load_all

    load_all()
    if spec.type not in REGISTRY:
        raise ConfigError(f"unknown page type {spec.type!r} (known: {', '.join(sorted(REGISTRY))})")
    page = REGISTRY[spec.type](spec.options)
    page.duration = spec.duration
    return page
