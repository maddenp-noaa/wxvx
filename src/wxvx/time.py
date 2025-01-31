from __future__ import annotations

from datetime import datetime, timedelta
from itertools import product
from typing import Optional, overload

from wxvx.util import WXVXError

# Public


class ValidTime:

    def __init__(self, cycle: datetime, leadtime: Optional[timedelta] = None):
        self.cycle = cycle
        self.leadtime = leadtime or timedelta(hours=0)
        self.t = self.cycle + self.leadtime
        self.hh = hh(self.t)
        self.yyyymmdd = yyyymmdd(self.t)

    def __eq__(self, other):
        return hash(self) == hash(other)

    def __hash__(self):
        return int(self.t.timestamp())

    def __lt__(self, other):
        return hash(self) < hash(other)

    def __repr__(self):
        return self.t.isoformat()


def hh(dt: datetime) -> str:
    return dt.strftime("%H")


def validtimes(cycles: dict[str, str], leadtimes: dict[str, str]) -> list[ValidTime]:
    range_params = lambda section: [section[param] for param in ("start", "step", "stop")]
    cycles_start, cycles_step, cycles_stop = range_params(cycles)
    leadtimes_start, leadtimes_step, leadtimes_stop = range_params(leadtimes)
    pairs = product(
        _cycles(start=cycles_start, step=cycles_step, stop=cycles_stop),
        _leadtimes(leadtimes_start, leadtimes_step, leadtimes_stop),
    )
    return sorted(set(ValidTime(cycle=cycle, leadtime=leadtime) for cycle, leadtime in pairs))


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
    td = timedelta(**args)
    return td
