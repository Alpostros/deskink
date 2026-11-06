from datetime import datetime
from pathlib import Path

import pytest

from deskink import config
from deskink.config import ConfigError, QuietHours, parse

ROOT = Path(__file__).resolve().parents[1]


def test_example_config_loads():
    cfg = config.load(ROOT / "config.example.toml")
    assert [p.type for p in cfg.pages] == ["trains", "weather", "homelab"]
    assert all(p.duration == 30 for p in cfg.pages)
    assert cfg.quiet_hours.show == "blank"


def test_per_page_duration_overrides_default():
    cfg = parse({"default_duration": 20, "pages": [{"type": "clock"}, {"type": "clock", "duration": 45}]})
    assert [p.duration for p in cfg.pages] == [20, 45]


def test_disabled_pages_are_skipped():
    cfg = parse({"pages": [{"type": "clock", "enabled": False}, {"type": "weather"}]})
    assert [p.type for p in cfg.pages] == ["weather"]


@pytest.mark.parametrize("raw, match", [
    ({}, "no enabled"),
    ({"pages": [{"duration": 5}]}, "missing type"),
    ({"pages": [{"type": "clock", "duration": 0}]}, "positive"),
    ({"pages": [{"type": "clock"}], "display": {"driver": "lcd"}}, "driver"),
    ({"pages": [{"type": "clock"}], "display": {"full_refresh_every": 0}}, "full_refresh_every"),
    ({"pages": [{"type": "clock"}], "quiet_hours": {"start": "25:00", "end": "07:00"}}, "HH:MM"),
    ({"pages": [{"type": "clock"}], "quiet_hours": {"start": "07:00"}}, "both"),
])
def test_invalid_configs(raw, match):
    with pytest.raises(ConfigError, match=match):
        parse(raw)


def at(hh, mm):
    return datetime(2026, 11, 6, hh, mm)


def test_quiet_hours_across_midnight():
    q = QuietHours(at(0, 30).time(), at(7, 0).time())
    assert q.active(at(0, 30))
    assert q.active(at(3, 0))
    assert not q.active(at(7, 0))
    assert not q.active(at(0, 29))
    assert q.seconds_left(at(6, 0)) == 3600


def test_quiet_hours_wrapping_midnight():
    q = QuietHours(at(23, 0).time(), at(6, 0).time())
    assert q.active(at(23, 30))
    assert q.active(at(1, 0))
    assert not q.active(at(12, 0))
    assert q.seconds_left(at(23, 0)) == 7 * 3600


def test_cli_accepts_config_on_either_side(capsys):
    from deskink.__main__ import main

    example = str(ROOT / "config.example.toml")
    assert main(["-c", example, "list"]) == 0
    assert main(["list", "-c", example]) == 0
    assert capsys.readouterr().out.count("Delft") == 2
