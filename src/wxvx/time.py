"""
Routines for computing cycles, leadtimes, etc.
"""

from datetime import datetime, timedelta
from itertools import product
from typing import overload

# Public


def cycles(config: dict) -> list[datetime]:
    start, stop = [datetime.fromisoformat(config["cycles"][key]) for key in ("start", "stop")]
    step = _delta(config["cycles"]["step"])
    return _enumerate(start, stop, step)


def leadtimes(config: dict) -> list[timedelta]:
    start, stop = [_delta(config["leadtimes"][key]) for key in ("start", "stop")]
    step = _delta(config["leadtimes"]["step"])
    return _enumerate(start, stop, step)


def validtimes(config: dict) -> list[datetime]:
    return [cycle + leadtime for cycle, leadtime in product(cycles(config), leadtimes(config))]


# Private


def _delta(step: str) -> timedelta:
    keys = ["hours", "minutes", "seconds"]
    args = dict(zip(keys, map(int, step.split(":"))))
    return timedelta(**args)


@overload
def _enumerate(start: datetime, stop: datetime, step: timedelta) -> list[datetime]: ...
@overload
def _enumerate(start: timedelta, stop: timedelta, step: timedelta) -> list[timedelta]: ...
def _enumerate(start, stop, step):
    xs = [start]
    while (x := xs[-1]) < stop:
        xs.append(x + step)
    return xs
