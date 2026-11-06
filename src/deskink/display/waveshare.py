import logging
import os
import sys
import time

from PIL import Image

log = logging.getLogger(__name__)

DRIVER_DIR = os.environ.get("DESKINK_DRIVER_DIR", "/opt/deskink/vendor")


def load_driver():
    if DRIVER_DIR not in sys.path:
        sys.path.insert(0, DRIVER_DIR)
    from waveshare_epd import epd2in13_V4

    return epd2in13_V4


class WaveshareV4:
    def __init__(self, flip: bool = False):
        self.flip = flip
        self.epd = load_driver().EPD()
        self.awake = False

    def show(self, img: Image.Image, full: bool) -> None:
        if self.flip:
            img = img.rotate(180)
        buf = self.epd.getbuffer(img)
        if full or not self.awake:
            if self.awake:
                self.epd.sleep()
            self.epd.init()
            self.awake = True
            self.epd.displayPartBaseImage(buf)
        else:
            self.epd.displayPartial(buf)

    def sleep(self) -> None:
        if self.awake:
            self.epd.sleep()
            self.awake = False

    def close(self) -> None:
        self.sleep()


def selftest(min_seconds: float = 1.0) -> tuple[bool, float]:
    epd = load_driver().EPD()
    epd.init()
    t0 = time.monotonic()
    epd.Clear(0xFF)
    took = time.monotonic() - t0
    epd.sleep()
    return took >= min_seconds, took
