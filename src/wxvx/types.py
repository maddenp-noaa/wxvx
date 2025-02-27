# noqa: A005

from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path


@dataclass
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

    def __eq__(self, other):
        return all(
            getattr(self, k) == getattr(other, k)
            for k in ["baseline", "cycles", "forecast", "leadtimes", "variables", "workdir"]
        )


@dataclass
class Cycles:
    start: str
    step: str
    stop: str


class Forecast:
    def __init__(self, name: str, path: str):
        self.name = name
        self.path = Path(path)

    def __eq__(self, other):
        return all(getattr(self, k) == getattr(other, k) for k in ["name", "path"])


@dataclass
class Leadtimes:
    start: str
    step: str
    stop: str


@dataclass
class Plot:
    baseline: bool


Source = Enum("Source", [("BASELINE", auto()), ("FORECAST", auto())])
