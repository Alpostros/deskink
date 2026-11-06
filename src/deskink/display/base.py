from typing import Protocol

from PIL import Image


class Display(Protocol):
    def show(self, img: Image.Image, full: bool) -> None: ...

    def sleep(self) -> None: ...

    def close(self) -> None: ...
