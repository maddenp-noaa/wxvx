"""
Tests for wxvx.time.
"""

# pylint: disable=invalid-name,protected-access

from datetime import datetime, timedelta

from pytest import mark, raises

from wxvx import time
from wxvx.util import WXVXError

# Tests


def test_time_ValidTime():
    cycle = datetime(2024, 1, 28, 12)
    leadtime = timedelta(hours=1)
    validtime = time.ValidTime(cycle=cycle, leadtime=leadtime)
    assert hash(validtime) == (cycle + leadtime).timestamp()
    assert validtime < time.ValidTime(cycle=cycle, leadtime=timedelta(hours=2))
    assert validtime == time.ValidTime(cycle=cycle, leadtime=timedelta(hours=1))
    assert validtime > time.ValidTime(cycle=cycle, leadtime=timedelta(hours=0))
    assert repr(validtime) == "2024-01-28T13:00:00"
    assert validtime.hh == "13"
    assert validtime.iso == "2024-01-28T13:00:00"
    assert validtime.timestamp == 1706446800
    assert validtime.yyyymmdd == "20240128"


def test_time_validtimes(config):
    actual = set(
        x.validtime for x in time.validtimes(cycles=config["cycles"], leadtimes=config["leadtimes"])
    )
    expected = {
        datetime(2024, 12, 19, 18),
        datetime(2024, 12, 20, 0),
        datetime(2024, 12, 20, 6),
        datetime(2024, 12, 20, 12),
        datetime(2024, 12, 20, 18),
    }
    assert actual == expected


def test_time__cycles(config):
    assert time._cycles(**config["cycles"]) == [
        datetime(2024, 12, 19, 18),
        datetime(2024, 12, 20, 6),
    ]


def test_time__enumerate_basic():
    start = datetime(2024, 12, 19, 12, 0)
    step = timedelta(hours=6)
    stop = datetime(2024, 12, 20, 6, 0)
    assert time._enumerate(start=start, stop=stop, step=step) == [
        datetime(2024, 12, 19, 12, 0),
        datetime(2024, 12, 19, 18, 0),
        datetime(2024, 12, 20, 0, 0),
        datetime(2024, 12, 20, 6, 0),
    ]


def test_time__enumerate_degenerate_one():
    start = datetime(2024, 12, 19, 12, 0)
    step = timedelta(hours=6)
    stop = datetime(2024, 12, 19, 12, 0)
    assert time._enumerate(start=start, step=step, stop=stop) == [datetime(2024, 12, 19, 12, 0)]


def test_time__enumerate_stop_precedes_start():
    start = datetime(2024, 12, 19, 12, 0)
    step = timedelta(hours=6)
    stop = datetime(2024, 12, 19, 6, 0)
    with raises(WXVXError) as e:
        time._enumerate(start=start, step=step, stop=stop)
    assert str(e.value) == "Stop time 2024-12-19 06:00:00 precedes start time 2024-12-19 12:00:00"


def test_time__leadtimes(config):
    assert time._leadtimes(**config["leadtimes"]) == [timedelta(hours=n) for n in (0, 6, 12)]


@mark.parametrize(
    "step,expected",
    [
        ("01:02:03", timedelta(hours=1, minutes=2, seconds=3)),
        ("168:00:00", timedelta(days=7)),
    ],
)
def test_time__timedelta(step, expected):
    assert time._timedelta(step=step) == expected
