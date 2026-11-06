import http.server
import threading
from datetime import datetime, timedelta

import pytest

from deskink.cache import Entry
from deskink.config import ConfigError, PageSpec
from deskink.frame import compose
from deskink.pages import REGISTRY, build, fixture, load_all, register
from deskink.pages.homelab import DOWN, UNKNOWN, UP, Check, HomelabPage, probe
from deskink.pages.trains import parse as parse_trains
from deskink.pages.trains import ts
from deskink.pages.weather import beaufort, compass
from deskink.pages.weather import parse as parse_weather

NOW = datetime(2026, 11, 6, 14, 30)
CHECKS = [{"name": f"svc{i}", "url": f"http://127.0.0.1:1/{i}"} for i in range(18)]
SPECS = [
    PageSpec("clock", 30),
    PageSpec("trains", 30, {"station": "DT"}),
    PageSpec("weather", 30),
    PageSpec("homelab", 30, {"checks": CHECKS}),
]


def test_registry_has_builtin_pages():
    assert {"clock", "trains", "weather", "homelab"} <= set(load_all())


def test_register_twice_fails():
    load_all()
    with pytest.raises(ValueError):
        register("clock")(type("Dup", (), {}))


def test_unknown_page_type_and_option():
    with pytest.raises(ConfigError, match="unknown page type"):
        build(PageSpec("nope", 30))
    with pytest.raises(ConfigError, match="unknown option"):
        build(PageSpec("weather", 30, {"colour": "red"}))
    with pytest.raises(ConfigError, match="station"):
        build(PageSpec("trains", 30))


@pytest.mark.parametrize("spec", SPECS, ids=lambda s: s.type)
@pytest.mark.parametrize("state", ["sample", "empty", "error", "stale"])
def test_every_page_renders(spec, state):
    page = build(spec)
    entry = {
        "sample": Entry(page.sample(), 1000.0),
        "empty": Entry(),
        "error": Entry(error="URLError: timed out"),
        "stale": Entry(page.sample(), 1000.0, "URLError: timed out"),
    }[state]
    img = compose(page, entry, NOW, 1, 3, wall=1300.0)
    assert img.size == (250, 122) and img.mode == "1"
    assert 0 < img.histogram()[0] < 250 * 122


def test_render_bug_becomes_error_card():
    page = build(PageSpec("weather", 30))
    img = compose(page, Entry({"nonsense": True}, 1.0), NOW)
    assert img.size == (250, 122)


def test_trains_parse_fixture():
    raw = fixture("trains.json")
    now = ts("2026-11-06T14:31:00+0100")
    rows = parse_trains(raw, now, rows=4, min_minutes=4)
    assert [r["time"] for r in rows] == ["14:36", "14:39", "14:44", "14:47"]
    den_haag, rotterdam, _, leiden = rows
    assert den_haag["delay"] == 2 and den_haag["direction"] == "Den Haag C."
    assert rotterdam["track"] == "3" and rotterdam["track_changed"]
    assert leiden["cancelled"]


def test_trains_filters():
    raw = fixture("trains.json")
    now = ts("2026-11-06T14:00:00+0100")
    only = parse_trains(raw, now, rows=6, only=["rotterdam"])
    assert {r["direction"] for r in only} == {"Rotterdam C."}
    rest = parse_trains(raw, now, rows=6, exclude=["Rotterdam", "Schiphol"], short=False)
    assert "Schiphol Airport" not in {r["direction"] for r in rest}
    assert len(rest) == 3


def test_trains_fetch_needs_key(monkeypatch):
    monkeypatch.delenv("NS_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="NS_API_KEY"):
        build(PageSpec("trains", 30, {"station": "DT"})).fetch()


def test_weather_parse_fixture():
    w = parse_weather(fixture("weather.json"))
    assert len(w["hours"]) == 3
    assert [h["time"] for h in w["hours"]] == ["15:00", "16:00", "17:00"]
    assert len(w["rain"]) == 12
    assert w["hours"][0]["kind"] == "rain"


def test_beaufort_and_compass():
    assert beaufort(0) == 0
    assert beaufort(8.3) == 2
    assert beaufort(120) == 12
    assert compass(0) == "N" and compass(120) == "SE" and compass(350) == "N"


def test_homelab_flap_guard():
    page = HomelabPage({"checks": CHECKS[:2], "fail_threshold": 2})
    assert {r["state"] for r in page.apply({"svc0": UP, "svc1": UP})} == {UP}
    assert page.apply({"svc0": DOWN, "svc1": UP})[0]["state"] == UP
    assert page.apply({"svc0": DOWN, "svc1": UP})[0]["state"] == DOWN
    assert page.apply({"svc0": UP, "svc1": UP})[0]["state"] == UP
    assert page.status(page.apply({"svc0": DOWN, "svc1": DOWN})) == "2/2 up"
    assert page.status(page.apply({"svc0": DOWN, "svc1": DOWN})) == "2 DOWN"


def test_homelab_check_validation():
    with pytest.raises(ConfigError, match="exactly one"):
        Check.from_options({"name": "x", "url": "http://a", "tcp": "a:1"}, 3)
    with pytest.raises(ConfigError, match="unknown key"):
        Check.from_options({"name": "x", "url": "http://a", "port": 1}, 3)
    with pytest.raises(ConfigError, match="at most 18"):
        HomelabPage({"checks": CHECKS + [{"name": "extra", "tcp": "a:1"}]})


@pytest.fixture
def server():
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            code, body = {"/ok": (200, b"pong"), "/redirect": (302, b""), "/boom": (500, b"no")}.get(
                self.path, (404, b""))
            self.send_response(code)
            if code == 302:
                self.send_header("Location", "/ok")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def test_probes_against_local_server(server):
    base = f"http://{server}"
    assert probe(Check("a", url=f"{base}/ok", contains="pong")) == UP
    assert probe(Check("b", url=f"{base}/ok", contains="nope")) == DOWN
    assert probe(Check("c", url=f"{base}/redirect")) == UP
    assert probe(Check("d", url=f"{base}/boom")) == DOWN
    assert probe(Check("e", tcp=server)) == UP
    assert probe(Check("f", tcp="127.0.0.1:1", timeout=0.5)) == DOWN
    assert probe(Check("g", prom='up{job="x"}')) == UNKNOWN
    assert probe(Check("h", prom="up", timeout=0.5), prometheus="http://127.0.0.1:1") == UNKNOWN


def test_trains_sample_is_relative_to_fixture():
    page = build(PageSpec("trains", 30, {"station": "DT", "min_minutes": 0}))
    first = ts(fixture("trains.json")["payload"]["departures"][0]["plannedDateTime"])
    assert page.sample()[0]["time"] == f"{first:%H:%M}"
    assert first - timedelta(minutes=1) < first
    assert REGISTRY["trains"] is type(page)
