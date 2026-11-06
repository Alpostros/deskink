import importlib
import pkgutil

from .base import REGISTRY, Canvas, Page, build, fixture, register

__all__ = ["REGISTRY", "Canvas", "Page", "build", "fixture", "register", "load_all"]


def load_all() -> dict[str, type[Page]]:
    for mod in pkgutil.iter_modules(__path__):
        if mod.name != "base":
            importlib.import_module(f"{__name__}.{mod.name}")
    return REGISTRY
