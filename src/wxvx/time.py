from dataclasses import dataclass
from datetime import datetime, timedelta
from itertools import product
from typing import overload

from wxvx.util import WXVXError

# Public


@dataclass
class TimeCoords:
    dt: datetime

    def __hash__(self):
        return int(self.dt.timestamp())

    def __lt__(self, other):
        return self.dt < other.dt

    def __repr__(self):
        return self.iso

    @property
    def hh(self) -> str:
        return self.dt.strftime("%H")

    @property
    def iso(self) -> str:
        return self.dt.isoformat()

    @property
    def yyyymmdd(self) -> str:
        return self.dt.strftime("%Y%m%d")


def validtimes(cycles: dict[str, str], leadtimes: dict[str, str]) -> list[TimeCoords]:
    cycles_start, cycles_step, cycles_stop = [cycles[x] for x in ("start", "step", "stop")]
    leadtimes_start, leadtimes_step, leadtimes_stop = [
        leadtimes[x] for x in ("start", "step", "stop")
    ]
    pairs = product(
        _cycles(start=cycles_start, step=cycles_step, stop=cycles_stop),
        _leadtimes(leadtimes_start, leadtimes_step, leadtimes_stop),
    )
    return sorted(set(TimeCoords(cycle + leadtime) for cycle, leadtime in pairs))


# Private


def _cycles(start: str, step: str, stop: str) -> list[datetime]:
    dt_start, dt_stop = [datetime.fromisoformat(x) for x in (start, stop)]
    td_step = _timedelta(step)
    return _enumerate(dt_start, dt_stop, td_step)


@overload
def _enumerate(start: datetime, stop: datetime, step: timedelta) -> list[datetime]: ...
@overload
def _enumerate(start: timedelta, stop: timedelta, step: timedelta) -> list[timedelta]: ...
def _enumerate(start, stop, step):
    if stop < start:
        raise WXVXError("Stop time %s precedes start time %s" % (stop, start))
    xs = [start]
    while (x := xs[-1]) < stop:
        xs.append(x + step)
    return xs


def _leadtimes(start: str, step: str, stop: str) -> list[timedelta]:
    td_start, td_step, td_stop = [_timedelta(x) for x in (start, step, stop)]
    return _enumerate(td_start, td_stop, td_step)


def _timedelta(step: str) -> timedelta:
    keys = ["hours", "minutes", "seconds"]
    args = dict(zip(keys, map(int, step.split(":"))))
    td = timedelta(**args)
    return td
