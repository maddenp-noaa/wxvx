from __future__ import annotations

from datetime import datetime, timedelta
from itertools import product
from typing import TYPE_CHECKING, overload

from wxvx.util import WXVXError

if TYPE_CHECKING:
    from collections.abc import Iterator

    from wxvx.types import Cycles, Leadtimes

# Public


class TimeCoords:
    """
    Time coordinates.
    """

    def __init__(self, cycle: datetime, leadtime: int | timedelta = 0):
        self.cycle = cycle.replace(tzinfo=None)  # All wxvx times are UTC
        self.leadtime = timedelta(hours=leadtime) if isinstance(leadtime, int) else leadtime
        self.validtime = self.cycle + self.leadtime
        self.yyyymmdd = yyyymmdd(self.validtime)
        self.hh = hh(self.validtime)

    def __eq__(self, other):
        return hash(self) == hash(other)

    def __hash__(self):
        return int(self.validtime.timestamp())

    def __lt__(self, other):
        return hash(self) < hash(other)

    def __repr__(self):
        return self.validtime.isoformat()


def hh(dt: datetime) -> str:
    return dt.strftime("%H")


def tcinfo(tc: TimeCoords, leadtime_digits: int = 3) -> tuple[str, str, str]:
    fmt = f"%0{leadtime_digits}d"
    return (yyyymmdd(dt=tc.cycle), hh(dt=tc.cycle), fmt % (tc.leadtime.total_seconds() // 3600))


def validtimes(cycles: Cycles | datetime, leadtimes: Leadtimes) -> Iterator[TimeCoords]:
    # pairs = product(
    #     [cycles]
    #     if isinstance(cycles, datetime)
    #     else _cycles(start=cycles.start, step=cycles.step, stop=cycles.stop),
    #     _leadtimes(leadtimes.start, leadtimes.step, stop=leadtimes.stop),
    # )
    for cycle, leadtime in product(
        [cycles]
        if isinstance(cycles, datetime)
        else _cycles(start=cycles.start, step=cycles.step, stop=cycles.stop),
        _leadtimes(leadtimes.start, leadtimes.step, stop=leadtimes.stop),
    ):
        yield TimeCoords(cycle=cycle, leadtime=leadtime)


def yyyymmdd(dt: datetime) -> str:
    return dt.strftime("%Y%m%d")


# Private


def _cycles(start: str, step: str, stop: str) -> list[datetime]:
    dt_start, dt_stop = [datetime.fromisoformat(x) for x in (start, stop)]
    td_step = _timedelta(step)
    return _enumerate(dt_start, td_step, dt_stop)


@overload
def _enumerate(start: datetime, step: timedelta, stop: datetime) -> list[datetime]: ...
@overload
def _enumerate(start: timedelta, step: timedelta, stop: timedelta) -> list[timedelta]: ...
def _enumerate(start, step, stop):
    if stop < start:
        raise WXVXError("Stop time %s precedes start time %s" % (stop, start))
    xs = [start]
    while (x := xs[-1]) < stop:
        xs.append(x + step)
    return xs


def _leadtimes(start: str, step: str, stop: str) -> list[timedelta]:
    td_start, td_step, td_stop = [_timedelta(x) for x in (start, step, stop)]
    return _enumerate(td_start, td_step, td_stop)


def _timedelta(step: str) -> timedelta:
    keys = ["hours", "minutes", "seconds"]
    args = dict(zip(keys, map(int, step.split(":"))))
    return timedelta(**args)
