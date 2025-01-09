"""
Tests for wxvx.time.
"""

# pylint: disable=protected-access,redefined-outer-name

from datetime import datetime, timedelta

from pytest import fixture, mark, raises

from wxvx import time
from wxvx.util import WXVXError

# Fixtures


@fixture
def config():
    return {
        "cycles": {
            "start": "2024-12-19T18:00:00",
            "stop": "2024-12-20T06:00:00",
            "step": "12:00:00",
        },
        "leadtimes": {
            "start": "00:00:00",
            "stop": "12:00:00",
            "step": "06:00:00",
        },
    }


# Public


def test_time_cycles(config):
    assert time.cycles(config) == [datetime(2024, 12, 19, 18), datetime(2024, 12, 20, 6)]


def test_time_leadtimes(config):
    assert time.leadtimes(config) == [timedelta(hours=n) for n in (0, 6, 12)]


def test_time_validtimes(config):
    assert [x.dt for x in time.validtimes(config)] == [
        datetime(2024, 12, 19, 18),
        datetime(2024, 12, 20, 0),
        datetime(2024, 12, 20, 6),
        datetime(2024, 12, 20, 12),
        datetime(2024, 12, 20, 18),
    ]


# Private


@mark.parametrize(
    "step,expected",
    [
        ("01:02:03", timedelta(hours=1, minutes=2, seconds=3)),
        ("168:00:00", timedelta(days=7)),
    ],
)
def test_time__delta(step, expected):
    assert time._delta(step=step) == expected


def test_time__enumerate_basic():
    start = datetime(2024, 12, 19, 12, 0)
    stop = datetime(2024, 12, 20, 6, 0)
    assert time._enumerate(start=start, stop=stop, step=timedelta(hours=6)) == [
        start,
        datetime(2024, 12, 19, 18, 0),
        datetime(2024, 12, 20, 0, 0),
        stop,
    ]


def test_time__enumerate_degenerate_one():
    start = datetime(2024, 12, 19, 12, 0)
    assert time._enumerate(
        start=start,
        stop=datetime(2024, 12, 19, 12, 0),
        step=timedelta(hours=6),
    ) == [start]


def test_time__enumerate_stop_precedes_start():
    with raises(WXVXError) as e:
        time._enumerate(
            start=datetime(2024, 12, 19, 12, 0),
            stop=datetime(2024, 12, 19, 6, 0),
            step=timedelta(hours=6),
        )
    assert str(e.value) == "Stop time 2024-12-19 06:00:00 precedes start time 2024-12-19 12:00:00"
