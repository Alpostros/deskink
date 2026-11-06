from datetime import datetime, timedelta

from deskink.app import App, RefreshPolicy
from deskink.config import parse
from deskink.pages import Page, build


class FakeDisplay:
    def __init__(self):
        self.calls = []

    def show(self, img, full):
        self.calls.append(("full" if full else "partial", img))

    def sleep(self):
        self.calls.append(("sleep", None))

    def close(self):
        self.calls.append(("close", None))

    def kinds(self):
        return [k for k, _ in self.calls]


class Counting(Page):
    type = "counting"
    refresh_every = 0

    def __init__(self, title, duration):
        super().__init__({"title": title})
        self.duration = duration
        self.fetches = 0

    def fetch(self):
        self.fetches += 1
        return {"n": self.fetches}

    def render(self, data, c):
        c.draw.text((c.x + 5, c.y + 5), f"{self.title} {data['n']}", fill=0)


class Clock:
    def __init__(self, start):
        self.t = start

    def now(self):
        return self.t

    def wall(self):
        return self.t.timestamp()


def make_app(raw, pages, start, frames):
    cfg = parse(raw)
    display = FakeDisplay()
    clock = Clock(start)
    app = App(cfg, pages, display, now=clock.now, wall=clock.wall)
    waits = []

    def wait(seconds):
        waits.append(seconds)
        clock.t += timedelta(seconds=seconds)
        app.cache.pool.submit(lambda: None).result()
        if len(waits) >= frames:
            app.stop.set()

    app.wait = wait
    return app, display, waits, clock


def test_refresh_policy_cadence():
    p = RefreshPolicy(3)
    assert [p.next() for _ in range(7)] == [True, False, False, True, False, False, True]
    p.force_full()
    assert [p.next() for _ in range(3)] == [True, False, False]


def test_rotation_uses_each_page_duration():
    pages = [Counting("a", 30), Counting("b", 10), Counting("c", 45)]
    raw = {"pages": [{"type": "clock"}], "display": {"full_refresh_every": 4}}
    app, display, waits, _ = make_app(raw, pages, datetime(2026, 11, 6, 12, 0), frames=6)
    app.run()
    assert waits == [30, 10, 45, 30, 10, 45]
    assert display.kinds() == ["full", "partial", "partial", "partial", "full", "partial", "full", "close"]
    assert all(p.fetches >= 1 for p in pages)


def test_quiet_hours_blank_then_wake_with_full_refresh():
    pages = [Counting("a", 600)]
    raw = {"pages": [{"type": "clock"}], "display": {"full_refresh_every": 100},
           "quiet_hours": {"start": "00:30", "end": "07:00"}}
    app, display, waits, clock = make_app(raw, pages, datetime(2026, 11, 6, 0, 20), frames=3)
    app.run()
    kinds = display.kinds()
    assert kinds[:3] == ["full", "full", "sleep"]
    assert waits[1] == 60

    app2, display2, waits2, _ = make_app(raw, [Counting("a", 600)], datetime(2026, 11, 6, 6, 59, 30), frames=3)
    app2.run()
    assert display2.kinds()[:4] == ["full", "sleep", "full", "partial"]
    assert waits2[0] == 30


def test_quiet_hours_can_freeze_on_a_page():
    page = build(parse({"pages": [{"type": "clock", "title": "Clock"}]}).pages[0])
    raw = {"pages": [{"type": "clock"}], "quiet_hours": {"start": "00:00", "end": "07:00", "show": "Clock"}}
    app, display, _, _ = make_app(raw, [page], datetime(2026, 11, 6, 3, 0), frames=1)
    app.run()
    frozen = display.calls[0][1]
    assert frozen.histogram()[0] > 200


def test_stopped_frame_on_exit():
    app, display, _, _ = make_app({"pages": [{"type": "clock"}]}, [Counting("a", 30)],
                                  datetime(2026, 11, 6, 12, 0), frames=1)
    app.run()
    assert display.kinds()[-2:] == ["full", "close"]
