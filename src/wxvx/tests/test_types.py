from pathlib import Path

from pytest import fixture, raises

from wxvx import types

# Fixtures


@fixture
def baseline(config_data):
    return types.Baseline(**config_data["baseline"])


@fixture
def coords(config_data):
    return types.Coords(**config_data["forecast"]["coords"])


@fixture
def cycles(config_data):
    return types.Cycles(**config_data["cycles"])


@fixture
def forecast(config_data):
    return types.Forecast(**config_data["forecast"])


@fixture
def leadtimes(config_data):
    return types.Leadtimes(**config_data["leadtimes"])


@fixture
def time(config_data):
    return types.Time(**config_data["forecast"]["coords"]["time"])


# Tests


def test_Baseline(baseline, config_data):
    obj = baseline
    assert obj.name == "Baseline"
    assert obj.template == "https://some.url/{yyyymmdd}/{hh}/{fh:02}/a.grib2"
    cfg = config_data["baseline"]
    other1 = types.Baseline(**cfg)
    assert obj == other1
    other2 = types.Baseline(**{**cfg, "name": "foo"})
    assert obj != other2


def test_Config(baseline, config_data, cycles, forecast, leadtimes):
    obj = types.Config(config_data=config_data)
    assert hash(obj)
    assert obj.baseline == baseline
    assert obj.cycles == cycles
    assert obj.forecast == forecast
    assert obj.leadtimes == leadtimes
    assert obj.paths.grids_baseline == Path(config_data["paths"]["grids"]["baseline"])
    assert obj.paths.grids_forecast == Path(config_data["paths"]["grids"]["forecast"])
    assert obj.paths.run == Path(config_data["paths"]["run"])
    assert obj.variables == config_data["variables"]
    other = types.Config(config_data=config_data)
    assert obj == other
    other.variables = {}
    assert obj != other


def test_Coords(config_data, coords):
    obj = coords
    assert hash(obj)
    assert obj.latitude == "latitude"
    assert obj.level == "level"
    assert obj.longitude == "longitude"
    assert obj.time.inittime == "time"
    assert obj.time.leadtime == "lead_time"
    cfg = config_data["forecast"]["coords"]
    other1 = types.Coords(**cfg)
    assert obj == other1
    other2 = types.Coords(**{**cfg, "latitude": "lat"})
    assert obj != other2


def test_Cycles(config_data, cycles):
    obj = cycles
    assert obj.start == "2024-12-19T18:00:00"
    assert obj.step == "12:00:00"
    assert obj.stop == "2024-12-20T06:00:00"
    cfg = config_data["cycles"]
    other1 = types.Cycles(**cfg)
    assert obj == other1
    other2 = types.Cycles(**{**cfg, "step": "24:00:00"})
    assert obj != other2


def test_Forecast(config_data, forecast):
    obj = forecast
    assert hash(obj)
    assert obj.coords.latitude == "latitude"
    assert obj.coords.level == "level"
    assert obj.coords.longitude == "longitude"
    assert obj.coords.time.inittime == "time"
    assert obj.coords.time.leadtime == "lead_time"
    assert obj.name == "Forecast"
    assert obj.path == Path("/path/to/forecast")
    cfg = config_data["forecast"]
    other1 = types.Forecast(**cfg)
    assert obj == other1
    other2 = types.Forecast(**{**cfg, "name": "foo"})
    assert obj != other2


def test_Leadtimes(config_data, leadtimes):
    obj = leadtimes
    assert obj.start == "00:00:00"
    assert obj.step == "06:00:00"
    assert obj.stop == "12:00:00"
    cfg = config_data["leadtimes"]
    other1 = types.Leadtimes(**cfg)
    assert obj == other1
    other2 = types.Leadtimes(**{**cfg, "start": "01:00:00"})
    assert obj != other2


def test_Time(config_data, time):
    obj = time
    assert hash(obj)
    assert obj.inittime == "time"
    assert obj.leadtime == "lead_time"
    cfg = config_data["forecast"]["coords"]["time"]
    other1 = types.Time(**cfg)
    assert obj == other1
    other2 = types.Time(**{**cfg, "inittime": "foo"})
    assert obj != other2


def test_VarMeta():
    def fails(k, v):
        with raises(AssertionError):
            types.VarMeta(**{**kwargs, k: type(v)()})

    kwargs: dict = dict(
        cat_thresh=[">=20", ">=30", ">=40"],
        cf_standard_name="unknown",
        cnt_thresh=[">15"],
        description="Composite Reflectivity",
        level_type="atmosphere",
        met_stats=["FSS", "PODY"],
        name="refc",
        nbrhd_shape="CIRCLE",
        nbrhd_width=[3, 5, 11],
        units="dBZ",
    )
    x = types.VarMeta(**kwargs)
    for k, v in kwargs.items():
        assert getattr(x, k) == v
    # Must not be empty:
    for k, v in kwargs.items():
        fails(k, type(v)())
    # Must not have None values:
    for k in ["cf_standard_name", "description", "level_type", "met_stats", "name", "units"]:
        fails(k, None)
    # Must not have unrecognized values:
    for k, v in [
        ("level_type", "intergalactic"),
        ("met_stats", ["XYZ"]),
        ("nbrhd_shape", "TRIANGLE"),
    ]:
        fails(k, v)
