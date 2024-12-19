"""
Tests for wxvx.time.
"""

# pylint: disable=protected-access

from datetime import datetime, timedelta

from pytest import raises

from wxvx import time
from wxvx.util import WXVXError

# Public


def test_time_cycles():
    pass


def test_time_leadtimes():
    pass


def test_time_validtimes():
    pass


# Private


def test_time__delta():
    pass


def test_time__enumerate_basic():
    start = datetime(2024, 12, 19, 12, 0)
    stop = datetime(2024, 12, 20, 6, 0)
    step = timedelta(hours=6)
    assert time._enumerate(start, stop, step) == [
        start,
        datetime(2024, 12, 19, 18, 0),
        datetime(2024, 12, 20, 0, 0),
        stop,
    ]


def test_time__enumerate_degenerate_one():
    start = datetime(2024, 12, 19, 12, 0)
    stop = datetime(2024, 12, 19, 12, 0)
    step = timedelta(hours=6)
    assert time._enumerate(start, stop, step) == [start]


def test_time__enumerate_stop_precedes_start():
    start = datetime(2024, 12, 19, 12, 0)
    stop = datetime(2024, 12, 19, 6, 0)
    step = timedelta(hours=6)
    with raises(WXVXError) as e:
        time._enumerate(start, stop, step)
    assert str(e.value) == "Stop time 2024-12-19 06:00:00 precedes start time 2024-12-19 12:00:00"
