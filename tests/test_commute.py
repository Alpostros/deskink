import copy
import json

import pytest

from deskink.config import ConfigError, PageSpec
from deskink.pages import build, fixture
from deskink.pages.commute import parse, scrub

OPTS = {"origin": [52.0, 4.36], "destination": [51.92, 4.47]}


def page(**extra):
    return build(PageSpec("commute", 30, {**OPTS, **extra}))


def test_parse_fixture():
    d = parse(fixture("commute.json"))
    assert (d["minutes"], d["delay"], d["free"], d["usual"], d["arrive"], d["via"]) == (23, 7, 16, 19, "08:35", "A13")
    assert [(i["kind"], i["road"], i["delay"]) for i in d["incidents"]] == [("JAM", "A13", 5), ("WORKS", "A20", 2)]
    alt = d["alternative"]
    assert (alt["minutes"], alt["via"], alt["delay"]) == (26, "A4", 2)


def test_closure_sorts_first_and_tiny_delays_drop():
    raw = copy.deepcopy(fixture("commute.json"))
    raw["routes"][0]["sections"].append({"startPointIndex": 190, "endPointIndex": 200, "sectionType": "TRAFFIC",
                                         "simpleCategory": "ROAD_CLOSURE", "magnitudeOfDelay": 4})
    d = parse(raw)
    assert d["incidents"][0]["kind"] == "CLOSED" and d["incidents"][0]["closed"]
    assert "SLOW" not in {i["kind"] for i in d["incidents"]}


def test_single_route_and_no_route():
    raw = copy.deepcopy(fixture("commute.json"))
    raw["routes"] = raw["routes"][:1]
    assert parse(raw)["alternative"] is None
    with pytest.raises(ValueError):
        parse({"routes": []})


def test_scrub_removes_every_coordinate():
    raw = {"routes": [{"legs": [{"points": [{"latitude": 52.1, "longitude": 4.3}]}],
                       "guidance": {"instructions": [{"point": {"latitude": 52.1, "longitude": 4.3},
                                                      "street": "Home Street", "roadNumbers": ["A13"]}]}}]}
    text = json.dumps(scrub(raw))
    assert "52.1" not in text and "Home Street" not in text and "A13" in text
    assert "latitude" not in json.dumps(fixture("commute.json"))


def test_url_has_traffic_params_and_key():
    url = page(alternatives=2).url("secret")
    assert "/52.000000,4.360000:51.920000,4.470000/json?" in url
    for part in ("key=secret", "traffic=true", "departAt=now", "computeTravelTimeFor=all", "sectionType=traffic",
                 "instructionsType=coded", "maxAlternatives=2"):
        assert part in url


@pytest.mark.parametrize("extra, match", [
    ({"origin": None}, "origin"),
    ({"destination": [95, 4]}, "out of range"),
    ({"destination": "Rotterdam"}, "destination"),
    ({"alternatives": 3}, "alternatives"),
    ({"refresh_every": 30}, "quota"),
])
def test_config_validation(extra, match):
    with pytest.raises(ConfigError, match=match):
        page(**extra)


def test_fetch_needs_key(monkeypatch):
    monkeypatch.delenv("TOMTOM_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="TOMTOM_API_KEY"):
        page().fetch()


def test_status_only_when_delayed():
    p = page()
    d = p.sample()
    assert p.status(d) == "+7 min"
    assert p.status(dict(d, delay=0)) is None


def test_delay_is_against_empty_roads_not_incidents():
    raw = copy.deepcopy(fixture("commute.json"))
    s = raw["routes"][0]["summary"]
    s.update(travelTimeInSeconds=1598, trafficDelayInSeconds=0, noTrafficTravelTimeInSeconds=1345,
             historicTrafficTravelTimeInSeconds=1641)
    d = parse(raw)
    assert (d["minutes"], d["delay"], d["free"], d["usual"]) == (27, 5, 22, 27)
    del s["historicTrafficTravelTimeInSeconds"], s["noTrafficTravelTimeInSeconds"]
    d = parse(raw)
    assert d["usual"] is None and d["free"] == 27 and d["delay"] == 0


def test_alert_compares_with_usual(monkeypatch):
    from datetime import datetime

    from deskink.cache import Entry
    from deskink.frame import compose

    p = page(alert_delay_min=5)
    base = p.sample()
    as_usual = compose(p, Entry(dict(base, minutes=19, usual=19), 1.0), datetime(2026, 11, 9, 8, 0))
    worse = compose(p, Entry(dict(base, minutes=25, usual=19), 1.0), datetime(2026, 11, 9, 8, 0))
    assert worse.histogram()[0] > as_usual.histogram()[0] + 1000
