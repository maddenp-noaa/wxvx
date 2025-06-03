"""
Tests for wxvx.times.
"""

from datetime import timedelta

from pytest import mark, raises

from wxvx import times
from wxvx.types import Cycles, Leadtimes
from wxvx.util import WXVXError

# Tests


@mark.parametrize("leadtime", [timedelta(hours=1), 1])
def test_times_TimeCoords(leadtime, utc):
    cycle = utc(2025, 1, 28, 12)
    tc = times.TimeCoords(cycle=cycle, leadtime=leadtime)
    ltobj = leadtime if isinstance(leadtime, timedelta) else timedelta(hours=leadtime)
    assert hash(tc) == (cycle + ltobj).timestamp()
    assert tc < times.TimeCoords(cycle=cycle, leadtime=timedelta(hours=2))
    assert tc == times.TimeCoords(cycle=cycle, leadtime=timedelta(hours=1))
    assert tc > times.TimeCoords(cycle=cycle, leadtime=timedelta(hours=0))
    assert repr(tc) == "2025-01-28T13:00:00"
    assert str(tc) == "2025-01-28T13:00:00"
    assert tc.hh == "13"
    assert tc.yyyymmdd == "20250128"


def test_times_TimeCoords__no_leadtime(utc):
    cycle = utc(2025, 1, 28, 12)
    tc = times.TimeCoords(cycle=cycle)
    assert hash(tc) == cycle.timestamp()
    assert tc < times.TimeCoords(cycle=cycle, leadtime=timedelta(hours=1))
    assert tc == times.TimeCoords(cycle=cycle, leadtime=timedelta(hours=0))
    assert tc > times.TimeCoords(cycle=cycle, leadtime=timedelta(hours=-1))
    assert repr(tc) == "2025-01-28T12:00:00"
    assert str(tc) == "2025-01-28T12:00:00"
    assert tc.hh == "12"
    assert tc.yyyymmdd == "20250128"


def test_times_gen_cycles(config_data, utc):
    cycles = [utc(2024, 12, 19, 18), utc(2024, 12, 20, 6)]
    assert times.gen_cycles(**config_data["cycles"]) == cycles


def test_times_gen_leadtimes(config_data):
    assert times.gen_leadtimes(**config_data["leadtimes"]) == [
        timedelta(hours=n) for n in (0, 6, 12)
    ]


def test_times_gen_validtimes(config_data, utc):
    actual = {
        vt.validtime
        for vt in times.gen_validtimes(
            cycles=Cycles(**config_data["cycles"]), leadtimes=Leadtimes(**config_data["leadtimes"])
        )
    }
    expected = {
        utc(2024, 12, 19, 18),
        utc(2024, 12, 20, 0),
        utc(2024, 12, 20, 6),
        utc(2024, 12, 20, 12),
        utc(2024, 12, 20, 18),
    }
    assert actual == expected


def test_times_hh(utc):
    assert times.hh(utc(2025, 1, 30, 6)) == "06"
    assert times.hh(utc(2025, 1, 30, 18)) == "18"


def test_times_tcinfo(utc):
    cycle = utc(2025, 2, 11, 3)
    leadtime = timedelta(hours=8)
    tc = times.TimeCoords(cycle=cycle, leadtime=leadtime)
    assert times.tcinfo(tc=tc) == ("20250211", "03", "008")
    assert times.tcinfo(tc=tc, leadtime_digits=2) == ("20250211", "03", "08")


def test_times_yyyymmdd(utc):
    assert times.yyyymmdd(utc(2025, 1, 30, 18)) == "20250130"


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


@mark.parametrize(
    ("step", "expected"),
    [
        ("01:02:03", timedelta(hours=1, minutes=2, seconds=3)),
        ("168:00:00", timedelta(days=7)),
    ],
)
def test_times__timedelta(step, expected):
    assert times._timedelta(value=step) == expected
