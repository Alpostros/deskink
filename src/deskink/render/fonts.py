import os
from functools import lru_cache
from importlib import resources

from PIL import ImageFont

REGULAR = "DejaVuSans.ttf"
BOLD = "DejaVuSans-Bold.ttf"


def _dirs():
    env = os.environ.get("DESKINK_FONT_DIR")
    if env:
        yield env
    yield str(resources.files("deskink").joinpath("assets/fonts"))
    yield "/usr/share/fonts/truetype/dejavu"


@lru_cache(maxsize=64)
def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    name = BOLD if bold else REGULAR
    for d in _dirs():
        try:
            return ImageFont.truetype(os.path.join(d, name), size, layout_engine=ImageFont.Layout.BASIC)
        except OSError:
            continue
    return ImageFont.load_default(size)
