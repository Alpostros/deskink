from .base import Display


def open_display(driver: str, flip: bool = False, png_path: str = "screen.png") -> Display:
    if driver == "png":
        from .png import PngDisplay

        return PngDisplay(png_path, flip)
    if driver == "waveshare":
        from .waveshare import WaveshareV4

        return WaveshareV4(flip)
    raise ValueError(f"unknown display driver {driver!r}")


__all__ = ["Display", "open_display"]
