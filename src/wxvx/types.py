# noqa: A005

import json
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path


@dataclass(frozen=True)
class Baseline:
    name: str
    template: str


class Config:
    def __init__(self, config_data: dict):
        self.baseline = Baseline(**config_data["baseline"])
        self.cycles = Cycles(**config_data["cycles"])
        self.forecast = Forecast(**config_data["forecast"])
        self.leadtimes = Leadtimes(**config_data["leadtimes"])
        self.plot = Plot(**config_data["plot"])
        self.variables = config_data["variables"]
        self.workdir = Path(config_data["workdir"])

    KEYS = ("baseline", "cycles", "forecast", "leadtimes", "variables", "workdir")

    def __eq__(self, other):
        return all(getattr(self, k) == getattr(other, k) for k in self.KEYS)

    def __hash__(self):
        h = None
        for k in self.KEYS:
            obj = getattr(self, k)
            try:
                h = hash((h, hash(obj)))
            except TypeError:
                h = hash((h, json.dumps(obj, sort_keys=True)))
        assert h is not None
        return h


@dataclass(frozen=True)
class Cycles:
    start: str
    step: str
    stop: str


class Forecast:
    def __init__(self, name: str, path: str):
        self.name = name
        self.path = Path(path)

    KEYS = ("name", "path")

    def __eq__(self, other):
        return all(getattr(self, k) == getattr(other, k) for k in self.KEYS)

    def __hash__(self):
        return hash(tuple(getattr(self, k) for k in self.KEYS))


@dataclass(frozen=True)
class Leadtimes:
    start: str
    step: str
    stop: str


@dataclass(frozen=True)
class Plot:
    baseline: bool


Source = Enum("Source", [("BASELINE", auto()), ("FORECAST", auto())])
