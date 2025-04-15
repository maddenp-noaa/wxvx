from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

import numpy as np
import xarray as xr
from pytest import fixture

from wxvx import times
from wxvx.types import Config


@fixture
def check_cf_metadata() -> Callable:
    def check(ds: xr.DataArray, name: str) -> bool:
        ok = [True]  # hopefully

        def check(x):
            ok[0] = ok[0] and x

        check(ds.attrs.get("Conventions") == "CF-1.8")
        da = ds[name]
        for k, v in [("standard_name", "geopotential_height"), ("units", "m")]:
            check(da.attrs.get(k) == v)
        for k, v in [("standard_name", "latitude"), ("units", "degrees_north")]:
            check(da.latitude.attrs.get(k) == v)
        check(da.forecast_reference_time.attrs.get("standard_name") == "forecast_reference_time")
        check(da.time.attrs.get("standard_name") == "time")
        return ok[0]

    return check


@fixture
def c(config_data, fakefs):
    grids_baseline, grids_forecast, run = [
        fakefs / x for x in ("grids/baseline", "grids/forecast", "run")
    ]
    grids_baseline.mkdir(parents=True)
    grids_forecast.mkdir(parents=True)
    run.mkdir()
    return Config(
        {
            **config_data,
            "paths": {
                "grids": {"baseline": str(grids_baseline), "forecast": str(grids_forecast)},
                "run": str(run),
            },
        }
    )


@fixture
def c_real_fs(config_data, tmp_path):
    grids_baseline, grids_forecast, run = [
        tmp_path / x for x in ("grids/baseline", "grids/forecast", "run")
    ]
    grids_baseline.mkdir(parents=True)
    grids_forecast.mkdir(parents=True)
    run.mkdir()
    return Config(
        {
            **config_data,
            "paths": {
                "grids": {"baseline": str(grids_baseline), "forecast": str(grids_forecast)},
                "run": str(run),
            },
        }
    )


@fixture
def config_data():
    return {
        "baseline": {
            "compare": True,
            "name": "Baseline",
            "template": "https://some.url/{yyyymmdd}/{hh}/{ff}/a.grib2",
        },
        "cycles": {
            "start": "2024-12-19T18:00:00",
            "step": "12:00:00",
            "stop": "2024-12-20T06:00:00",
        },
        "forecast": {
            "mask": [
                [52.61564933, 225.90452027],
                [52.61564933, 275.0],
                [21.138123, 275.0],
                [21.138123, 225.90452027],
            ],
            "name": "Forecast",
            "path": "/path/to/forecast",
            "projection": {
                "a": 6371229,
                "b": 6371229,
                "lat_0": 38.5,
                "lat_1": 38.5,
                "lat_2": 38.5,
                "lon_0": 262.5,
                "proj": "lcc",
            },
        },
        "leadtimes": {
            "start": "00:00:00",
            "step": "06:00:00",
            "stop": "12:00:00",
        },
        "paths": {
            "grids": {
                "baseline": "/path/to/grids/baseline",
                "forecast": "/path/to/grids/forecast",
            },
            "run": "/path/to/run",
        },
        "variables": {
            "HGT": {
                "level_type": "isobaricInhPa",
                "levels": [900],
                "name": "gh",
            },
            "REFC": {
                "level_type": "atmosphere",
                "name": "refc",
            },
            "SPFH": {
                "level_type": "isobaricInhPa",
                "levels": [900, 1000],
                "name": "q",
            },
            "T2M": {
                "level_type": "heightAboveGround",
                "levels": [2],
                "name": "2t",
            },
        },
    }


@fixture
def da() -> xr.DataArray:
    one = np.array([1], dtype="float32")
    return xr.DataArray(
        name="HGT",
        data=one.reshape((1, 1, 1, 1, 1)),
        dims=["latitude", "longitude", "level", "time", "lead_time"],
        coords=dict(
            latitude=(["latitude", "longitude"], one.reshape((1, 1))),
            longitude=(["latitude", "longitude"], one.reshape((1, 1))),
            level=(["level"], np.array([900], dtype="float32")),
            time=np.array([0], dtype="datetime64[ns]"),
            lead_time=np.array([0], dtype="timedelta64[ns]"),
        ),
    )


@fixture
def fakefs(fs):
    return Path(fs.create_dir("/test").path)


@fixture
def tc(da):
    cycle = datetime.fromtimestamp(int(da.time.values[0]), tz=timezone.utc)
    leadtime = timedelta(hours=int(da.lead_time.values[0]))
    return times.TimeCoords(cycle=cycle, leadtime=leadtime)


@fixture
def utc():
    def datetime_utc(*args, **kwargs) -> datetime:
        # See https://github.com/python/mypy/issues/6799
        dt = datetime(*args, **kwargs, tzinfo=timezone.utc)  # type: ignore[misc]
        return dt.replace(tzinfo=None)

    return datetime_utc
