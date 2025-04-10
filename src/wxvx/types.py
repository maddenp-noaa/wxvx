# noqa: A005

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Any

Source = Enum("Source", [("BASELINE", auto()), ("FORECAST", auto())])


@dataclass(frozen=True)
class Baseline:
    compare: bool
    name: str
    template: str


class Config:
    def __init__(self, config_data: dict):
        paths = config_data["paths"]
        grids = paths["grids"]
        self.baseline = Baseline(**config_data["baseline"])
        self.cycles = Cycles(**config_data["cycles"])
        self.forecast = Forecast(**config_data["forecast"])
        self.leadtimes = Leadtimes(**config_data["leadtimes"])
        self.paths = Paths(grids["baseline"], grids["forecast"], paths["run"])
        self.variables = config_data["variables"]

    KEYS = ("baseline", "cycles", "forecast", "leadtimes", "paths", "variables")

    def __eq__(self, other):
        return all(getattr(self, k) == getattr(other, k) for k in self.KEYS)

    def __hash__(self):
        return _hash(self)


@dataclass(frozen=True)
class Cycles:
    start: str
    step: str
    stop: str


@dataclass(frozen=True)
class Forecast:
    name: str
    path: Path
    projection: dict
    mask: tuple[tuple[float, float]] | None = None

    KEYS = ("mask", "name", "path", "projection")

    def __hash__(self):
        return _hash(self)

    def __post_init__(self):
        if self.mask:
            _force(self, "mask", tuple(tuple(x) for x in self.mask))
        _force(self, "path", Path(self.path))


@dataclass(frozen=True)
class Leadtimes:
    start: str
    step: str
    stop: str


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
class VarMeta:
    cf_standard_name: str
    description: str
    level_type: str
    met_linetypes: list[str]
    met_stat: str
    name: str
    units: str

    def __post_init__(self):
        for val in vars(self):
            assert val  # i.e. no empty strings
        assert self.level_type in ["atmosphere", "heightAboveGround", "isobaricInhPa", "surface"]
        for met_linetype in self.met_linetypes:
            assert met_linetype in ["cnt", "cts", "nbrcnt"]
        assert self.met_stat in ["RMSE", "PODY"]


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
