from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum, auto
from functools import cached_property
from pathlib import Path
from typing import Any, cast

from wxvx.util import LINETYPE, expand, to_datetime, to_timedelta

_DatetimeT = str | datetime
_TimedeltaT = str | int


Source = Enum("Source", [("BASELINE", auto()), ("FORECAST", auto())])


@dataclass(frozen=True)
class Baseline:
    compare: bool
    name: str
    template: str


class Config:
    def __init__(self, value: dict):
        paths = value["paths"]
        grids = paths["grids"]
        self.baseline = Baseline(**value["baseline"])
        self.cycles = Cycles(value["cycles"])
        self.forecast = Forecast(**value["forecast"])
        self.leadtimes = Leadtimes(value["leadtimes"])
        self.paths = Paths(grids["baseline"], grids["forecast"], paths["run"])
        self.variables = value["variables"]

    KEYS = ("baseline", "cycles", "forecast", "leadtimes", "paths", "variables")

    def __eq__(self, other):
        return all(getattr(self, k) == getattr(other, k) for k in self.KEYS)

    def __hash__(self):
        return _hash(self)

    def __repr__(self):
        parts = ["%s=%s" % (x, getattr(self, x)) for x in self.KEYS]
        return "%s(%s)" % (self.__class__.__name__, ", ".join(parts))


@dataclass(frozen=True)
class Coords:
    latitude: str
    level: str
    longitude: str
    time: Time

    KEYS = ("latitude", "level", "longitude", "time")

    def __hash__(self):
        return _hash(self)

    def __post_init__(self):
        if isinstance(self.time, dict):
            _force(self, "time", Time(**self.time))


class Cycles:
    def __init__(self, value: dict[str, str | int | datetime] | list[str | datetime]):
        self.value = value

    def __eq__(self, other):
        return self.cycles == other.cycles

    def __hash__(self):
        return hash(tuple(self.cycles))

    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__, self.value)

    @cached_property
    def cycles(self) -> list[datetime]:
        if isinstance(self.value, dict):
            dt_start, dt_stop = [
                to_datetime(cast(_DatetimeT, self.value[x])) for x in ("start", "stop")
            ]
            td_step = to_timedelta(cast(_TimedeltaT, self.value["step"]))
            return expand(dt_start, td_step, dt_stop)
        return list(map(to_datetime, self.value))


@dataclass(frozen=True)
class Forecast:
    coords: Coords
    name: str
    path: Path
    projection: dict
    mask: tuple[tuple[float, float]] | None = None

    KEYS = ("coords", "mask", "name", "path", "projection")

    def __hash__(self):
        return _hash(self)

    def __post_init__(self):
        if isinstance(self.coords, dict):
            coords = Coords(**self.coords)
            _force(self, "coords", coords)
        if self.mask:
            _force(self, "mask", tuple(tuple(x) for x in self.mask))
        _force(self, "path", Path(self.path))


class Leadtimes:
    def __init__(self, value: dict[str, str | int] | list[str | int]):
        self.value = value

    def __eq__(self, other):
        return self.leadtimes == other.leadtimes

    def __hash__(self):
        return hash(tuple(self.leadtimes))

    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__, self.value)

    @cached_property
    def leadtimes(self) -> list[timedelta]:
        if isinstance(self.value, dict):
            td_start, td_step, td_stop = [
                to_timedelta(cast(_TimedeltaT, self.value[x])) for x in ("start", "step", "stop")
            ]
            return expand(td_start, td_step, td_stop)
        return list(map(to_timedelta, self.value))


@dataclass(frozen=True)
class Paths:
    grids_baseline: Path
    grids_forecast: Path
    run: Path

    def __post_init__(self):
        _force(self, "grids_baseline", Path(self.grids_baseline))
        _force(self, "grids_forecast", Path(self.grids_forecast))
        _force(self, "run", Path(self.run))


@dataclass(frozen=True)
class Time:
    inittime: str
    leadtime: str | None = None
    validtime: str | None = None

    def __post_init__(self):
        assert self.leadtime is not None or self.validtime is not None


@dataclass(frozen=True)
class VarMeta:
    cf_standard_name: str
    description: str
    level_type: str
    met_stats: list[str]
    name: str
    units: str
    # Optional:
    cat_thresh: list[str] | None = None
    cnt_thresh: list[str] | None = None
    nbrhd_shape: str | None = None
    nbrhd_width: list[int] | None = None

    def __post_init__(self):
        for k, v in vars(self).items():
            match k:
                case "cat_thresh":
                    assert v is None or (v and all(isinstance(x, str) for x in v))
                case "cf_standard_name":
                    assert v
                case "cnt_thresh":
                    assert v is None or (v and all(isinstance(x, str) for x in v))
                case "description":
                    assert v
                case "level_type":
                    assert v in ("atmosphere", "heightAboveGround", "isobaricInhPa", "surface")
                case "met_stats":
                    assert v
                    assert all(x in LINETYPE for x in v)
                case "name":
                    assert v
                case "nbrhd_shape":
                    assert v is None or v in ("CIRCLE", "SQUARE")
                case "nbrhd_width":
                    assert v is None or (v and all(isinstance(x, int) for x in v))
                case "units":
                    assert v


# Helpers


def _force(obj: Any, name: str, val: Any) -> None:
    object.__setattr__(obj, name, val)


def _hash(obj: Any) -> int:
    h = None
    for k in obj.KEYS:
        x = getattr(obj, k)
        try:
            h = hash((h, hash(x)))
        except TypeError:
            h = hash((h, json.dumps(x, sort_keys=True)))
    assert h is not None
    return h
