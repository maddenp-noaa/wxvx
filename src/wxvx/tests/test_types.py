from pathlib import Path

from pytest import fixture

from wxvx import types

# Fixtures


@fixture
def baseline(config_data):
    return types.Baseline(**config_data["baseline"])


@fixture
def cycles(config_data):
    return types.Cycles(**config_data["cycles"])


@fixture
def forecast(config_data):
    return types.Forecast(**config_data["forecast"])


@fixture
def leadtimes(config_data):
    return types.Leadtimes(**config_data["leadtimes"])


# Tests


def test_Baseline(baseline, config_data):
    obj = baseline
    assert obj.name == "Baseline"
    assert obj.template == "https://some.url/path/to/a.grib2"
    other = types.Baseline(**config_data["baseline"])
    assert obj == other
    other.name = "foo"
    assert obj != other


def test_Cycles(config_data, cycles):
    obj = cycles
    assert obj.start == "2024-12-19T18:00:00"
    assert obj.step == "12:00:00"
    assert obj.stop == "2024-12-20T06:00:00"
    other = types.Cycles(**config_data["cycles"])
    assert obj == other
    other.step = "24:00:00"
    assert obj != other


def test_Forecast(config_data, forecast):
    obj = forecast
    assert obj.name == "Forecast"
    assert obj.path == Path("/path/to/forecast")
    other = types.Forecast(**config_data["forecast"])
    assert obj == other
    other.name = "foo"
    assert obj != other


def test_Leadtimes(config_data, leadtimes):
    obj = leadtimes
    assert obj.start == "00:00:00"
    assert obj.step == "06:00:00"
    assert obj.stop == "12:00:00"
    other = types.Leadtimes(**config_data["leadtimes"])
    assert obj == other
    other.start = "01:00:00"
    assert obj != other


def test_Config(baseline, config_data, cycles, forecast, leadtimes):
    obj = types.Config(config_data=config_data)
    assert obj.baseline == baseline
    assert obj.cycles == cycles
    assert obj.forecast == forecast
    assert obj.leadtimes == leadtimes
    assert obj.variables == config_data["variables"]
    assert obj.workdir == Path(config_data["workdir"])
    other = types.Config(config_data=config_data)
    assert obj == other
    other.workdir = Path("/other/path")
    assert obj != other
