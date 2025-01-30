from dataclasses import dataclass
from datetime import datetime, timedelta
from itertools import product
from typing import overload

from wxvx.util import WXVXError

# Public


@dataclass
class TimeCoords:
    cycle: datetime
    leadtime: timedelta

    def __eq__(self, other):
        return hash(self) == hash(other)

    def __hash__(self):
        return int(self.timestamp)

    def __lt__(self, other):
        return self.validtime < other.validtime

    def __repr__(self):
        return self.iso

    @property
    def hh(self) -> str:
        return self.validtime.strftime("%H")

    @property
    def iso(self) -> str:
        return self.validtime.isoformat()

    @property
    def timestamp(self) -> float:
        return self.validtime.timestamp()

    @property
    def yyyymmdd(self) -> str:
        return self.validtime.strftime("%Y%m%d")

    @property
    def validtime(self) -> datetime:
        return self.cycle + self.leadtime


def timecoords(cycles: dict[str, str], leadtimes: dict[str, str]) -> list[TimeCoords]:
    range_params = lambda section: [section[param] for param in ("start", "step", "stop")]
    cycles_start, cycles_step, cycles_stop = range_params(cycles)
    leadtimes_start, leadtimes_step, leadtimes_stop = range_params(leadtimes)
    pairs = product(
        _cycles(start=cycles_start, step=cycles_step, stop=cycles_stop),
        _leadtimes(leadtimes_start, leadtimes_step, leadtimes_stop),
    )
    return sorted(set(TimeCoords(cycle=cycle, leadtime=leadtime) for cycle, leadtime in pairs))


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
