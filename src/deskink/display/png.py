import logging
import os

from PIL import Image

log = logging.getLogger(__name__)


class PngDisplay:
    def __init__(self, path: str, flip: bool = False):
        self.path = path
        self.flip = flip
        self.frames = 0

    def show(self, img: Image.Image, full: bool) -> None:
        if self.flip:
            img = img.rotate(180)
        tmp = f"{self.path}.tmp.png"
        img.save(tmp)
        os.replace(tmp, self.path)
        self.frames += 1
        log.info("frame %d -> %s (%s refresh)", self.frames, self.path, "full" if full else "partial")

    def sleep(self) -> None:
        log.info("display asleep")

    def close(self) -> None:
        pass
