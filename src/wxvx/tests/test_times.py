"""
Tests for wxvx.times.
"""

from datetime import timedelta

from pytest import mark, raises

from wxvx import times
from wxvx.util import WXVXError

# Tests


def test_times_ValidTime(utc):
    cycle = utc(2025, 1, 28, 12)
    leadtime = timedelta(hours=1)
    validtime = times.ValidTime(cycle=cycle, leadtime=leadtime)
    assert hash(validtime) == (cycle + leadtime).timestamp()
    assert validtime < times.ValidTime(cycle=cycle, leadtime=timedelta(hours=2))
    assert validtime == times.ValidTime(cycle=cycle, leadtime=timedelta(hours=1))
    assert validtime > times.ValidTime(cycle=cycle, leadtime=timedelta(hours=0))
    assert repr(validtime) == "2025-01-28T13:00:00"
    assert validtime.hh == "13"
    assert validtime.yyyymmdd == "20250128"


def test_times_ValidTime_no_leadtime(utc):
    cycle = utc(2025, 1, 28, 12)
    validtime = times.ValidTime(cycle=cycle)
    assert hash(validtime) == cycle.timestamp()
    assert validtime < times.ValidTime(cycle=cycle, leadtime=timedelta(hours=1))
    assert validtime == times.ValidTime(cycle=cycle, leadtime=timedelta(hours=0))
    assert validtime > times.ValidTime(cycle=cycle, leadtime=timedelta(hours=-1))
    assert repr(validtime) == "2025-01-28T12:00:00"
    assert validtime.hh == "12"
    assert validtime.yyyymmdd == "20250128"


def test_times_hh(utc):
    assert times.hh(utc(2025, 1, 30, 6)) == "06"
    assert times.hh(utc(2025, 1, 30, 18)) == "18"


def test_times_validtimes(config, utc):
    actual = {x.t for x in times.validtimes(cycles=config["cycles"], leadtimes=config["leadtimes"])}
    expected = {
        utc(2024, 12, 19, 18),
        utc(2024, 12, 20, 0),
        utc(2024, 12, 20, 6),
        utc(2024, 12, 20, 12),
        utc(2024, 12, 20, 18),
    }
    assert actual == expected


def test_times_yyyymmdd(utc):
    assert times.yyyymmdd(utc(2025, 1, 30, 18)) == "20250130"


def test_times__cycles(config, utc):
    assert times._cycles(**config["cycles"]) == [
        utc(2024, 12, 19, 18),
        utc(2024, 12, 20, 6),
    ]


def test_times__enumerate_basic(utc):
    start = utc(2024, 12, 19, 12, 0)
    step = timedelta(hours=6)
    stop = utc(2024, 12, 20, 6, 0)
    assert times._enumerate(start=start, stop=stop, step=step) == [
        utc(2024, 12, 19, 12, 0),
        utc(2024, 12, 19, 18, 0),
        utc(2024, 12, 20, 0, 0),
        utc(2024, 12, 20, 6, 0),
    ]


def test_times__enumerate_degenerate_one(utc):
    start = utc(2024, 12, 19, 12, 0)
    step = timedelta(hours=6)
    stop = utc(2024, 12, 19, 12, 0)
    assert times._enumerate(start=start, step=step, stop=stop) == [utc(2024, 12, 19, 12, 0)]


def test_times__enumerate_stop_precedes_start(utc):
    start = utc(2024, 12, 19, 12, 0)
    step = timedelta(hours=6)
    stop = utc(2024, 12, 19, 6, 0)
    with raises(WXVXError) as e:
        times._enumerate(start=start, step=step, stop=stop)
    assert str(e.value) == "Stop time 2024-12-19 06:00:00 precedes start time 2024-12-19 12:00:00"


def test_times__leadtimes(config):
    assert times._leadtimes(**config["leadtimes"]) == [timedelta(hours=n) for n in (0, 6, 12)]


@mark.parametrize(
    ("step", "expected"),
    [
        ("01:02:03", timedelta(hours=1, minutes=2, seconds=3)),
        ("168:00:00", timedelta(days=7)),
    ],
)
def test_times__timedelta(step, expected):
    assert times._timedelta(step=step) == expected
