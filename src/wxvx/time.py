from datetime import datetime, timedelta
from itertools import product
from types import SimpleNamespace as ns
from typing import overload

from wxvx.util import WXVXError

# Public


def cycles(config: dict) -> list[datetime]:
    start, stop = [datetime.fromisoformat(config["cycles"][key]) for key in ("start", "stop")]
    step = _delta(config["cycles"]["step"])
    return _enumerate(start, stop, step)


def leadtimes(config: dict) -> list[timedelta]:
    start, stop = [_delta(config["leadtimes"][key]) for key in ("start", "stop")]
    step = _delta(config["leadtimes"]["step"])
    return _enumerate(start, stop, step)


def timecoords(dt: datetime) -> ns:
    return ns(yyyymmdd=dt.strftime("%Y%m%d"), hh=dt.strftime("%H"), iso=dt.isoformat())


def validtimes(config: dict) -> list[datetime]:
    pairs = product(cycles(config), leadtimes(config))
    return sorted(set(cycle + leadtime for cycle, leadtime in pairs))


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
