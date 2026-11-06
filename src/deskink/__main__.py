import argparse
import logging
import signal
import sys
import time
from datetime import datetime
from pathlib import Path

from . import config as config_mod
from .cache import Entry
from .config import ConfigError
from .frame import compose
from .pages import build, load_all

log = logging.getLogger("deskink")


def _pages(cfg):
    return [build(spec) for spec in cfg.pages]


def cmd_run(args) -> int:
    from .app import App
    from .display import open_display

    cfg = config_mod.load(config_mod.find_config(args.config))
    pages = _pages(cfg)
    driver = args.display or cfg.driver
    display = open_display(driver, cfg.flip, args.png or cfg.png_path)
    app = App(cfg, pages, display)

    def stop(signum, _frame):
        log.info("signal %d, stopping", signum)
        app.stop.set()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    app.run()
    return 0


def cmd_render(args) -> int:
    cfg = config_mod.load(config_mod.find_config(args.config))
    pages = _pages(cfg)
    selected = [(i, p) for i, p in enumerate(pages)
                if args.all or not args.page or args.page in (p.title, p.type)]
    if not selected:
        print(f"no page matches {args.page!r}", file=sys.stderr)
        return 2
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    for i, page in selected:
        if args.fixtures:
            entry = Entry(data=page.sample(), fetched_at=time.time())
        else:
            entry = Entry()
            try:
                entry.data, entry.fetched_at = page.fetch(), time.time()
            except Exception as exc:
                entry.error = f"{type(exc).__name__}: {exc}"
        img = compose(page, entry, now, i, len(pages), time.time())
        if args.flip and cfg.flip:
            img = img.rotate(180)
        path = out / f"{i + 1}-{page.type}.png"
        img.save(path)
        if args.scale > 1:
            big = img.convert("L").resize((img.width * args.scale, img.height * args.scale), 0)
            big.save(out / f"{i + 1}-{page.type}@{args.scale}x.png")
        print(f"{path}{'  ' + entry.error if entry.error else ''}")
    return 0


def cmd_list(args) -> int:
    print("page types:", ", ".join(sorted(load_all())))
    try:
        cfg = config_mod.load(config_mod.find_config(args.config))
    except ConfigError as e:
        print(f"(no config: {e})")
        return 0
    for i, page in enumerate(_pages(cfg)):
        print(f"{i + 1}. {page.title:<12} type={page.type:<8} duration={page.duration:g}s "
              f"refresh_every={page.refresh_every:g}s")
    return 0


def cmd_selftest(args) -> int:
    from .display.waveshare import selftest

    try:
        ok, took = selftest(args.min_seconds)
    except Exception as exc:
        print(f"FAIL: {type(exc).__name__}: {exc}")
        print("If the GPIO is busy, stop the service first: sudo systemctl stop deskink")
        return 1
    if ok:
        print(f"OK: panel answered, full refresh took {took * 1000:.0f} ms")
        return 0
    print(f"FAIL: full refresh returned after {took * 1000:.0f} ms, a real panel needs about 2000 ms.")
    print("The driver does not notice a missing panel. Check the flex cable latch, the HAT seating "
          "(pin 1 over pin 1) and the header solder joints.")
    return 1


def main(argv=None) -> int:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("-c", "--config", default=argparse.SUPPRESS,
                        help="config file (default: $DESKINK_CONFIG, ./config.toml, /etc/deskink/config.toml)")
    common.add_argument("-v", "--verbose", action="store_true", default=argparse.SUPPRESS)
    p = argparse.ArgumentParser(prog="deskink", description="Multi-page e-ink desk dashboard", parents=[common])
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", parents=[common], help="rotate pages on the display")
    r.add_argument("--display", choices=config_mod.DRIVERS, help="override display.driver")
    r.add_argument("--png", help="PNG path for the png display")
    r.set_defaults(func=cmd_run)

    s = sub.add_parser("render", parents=[common], help="render pages to PNG files and exit")
    s.add_argument("--page", help="page title or type (default: all)")
    s.add_argument("--all", action="store_true")
    s.add_argument("--fixtures", action="store_true", help="use bundled sample data instead of fetching")
    s.add_argument("--out", default="preview")
    s.add_argument("--scale", type=int, default=3, help="also write an upscaled copy for viewing")
    s.add_argument("--flip", action="store_true", help="apply display.flip like the panel would")
    s.set_defaults(func=cmd_render)

    sub.add_parser("list", parents=[common], help="list page types and configured pages").set_defaults(func=cmd_list)

    t = sub.add_parser("selftest", parents=[common], help="check that a panel is attached and answering")
    t.add_argument("--min-seconds", type=float, default=1.0)
    t.set_defaults(func=cmd_selftest)

    args = p.parse_args(argv)
    args.config = getattr(args, "config", None)
    args.verbose = getattr(args, "verbose", False)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(levelname)s %(name)s: %(message)s")
    try:
        return args.func(args)
    except ConfigError as e:
        print(f"config error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
