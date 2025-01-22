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


def cycles(config: dict) -> list[datetime]:
    start, stop = [datetime.fromisoformat(config["cycles"][key]) for key in ("start", "stop")]
    step = _delta(config["cycles"]["step"])
    return _enumerate(start, stop, step)


def leadtimes(config: dict) -> list[timedelta]:
    start, stop = [_delta(config["leadtimes"][key]) for key in ("start", "stop")]
    step = _delta(config["leadtimes"]["step"])
    return _enumerate(start, stop, step)


def validtimes(config: dict) -> list[TimeCoords]:
    pairs = product(cycles(config), leadtimes(config))
    return sorted(set(TimeCoords(cycle + leadtime) for cycle, leadtime in pairs))


# Private


def _delta(step: str) -> timedelta:
    keys = ["hours", "minutes", "seconds"]
    args = dict(zip(keys, map(int, step.split(":"))))
    td = timedelta(**args)
    return td


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
