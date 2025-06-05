from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

import numpy as np
import xarray as xr
from pytest import fixture

from wxvx import times
from wxvx.types import Config

logging.getLogger().setLevel(logging.DEBUG)


@fixture
def check_cf_metadata() -> Callable:
    def check(ds: xr.DataArray, name: str, level: float | None = None):
        assert ds.attrs["Conventions"] == "CF-1.8"
        level_actual = ds.attrs["level"]
        if level:
            assert level_actual == level
        else:
            assert np.isnan(level_actual)
        da = ds[name]
        for k, v in [("standard_name", "geopotential_height"), ("units", "m")]:
            assert da.attrs[k] == v
        for k, v in [("standard_name", "latitude"), ("units", "degrees_north")]:
            assert da.latitude.attrs[k] == v
        assert da.forecast_reference_time.attrs["standard_name"] == "forecast_reference_time"
        assert da.time.attrs["standard_name"] == "time"

    return check


@fixture
def c(config_data, fakefs, gen_config):
    return gen_config(config_data, fakefs)


@fixture
def c_real_fs(config_data, gen_config, tmp_path):
    return gen_config(config_data, tmp_path)


@fixture
def config_data():
    return {
        "baseline": {
            "compare": True,
            "name": "GFS",
            "url": "https://some.url/{yyyymmdd}/{hh}/{fh:02}/a.grib2",
        },
        "cycles": {
            "start": "2024-12-19T18:00:00",
            "step": "12:00:00",
            "stop": "2024-12-20T06:00:00",
        },
        "forecast": {
            "coords": {
                "latitude": "latitude",
                "level": "level",
                "longitude": "longitude",
                "time": {
                    "inittime": "time",
                    "leadtime": "lead_time",
                },
            },
            "mask": [
                [52.61564933, 225.90452027],
                [52.61564933, 275.0],
                [21.138123, 275.0],
                [21.138123, 225.90452027],
            ],
            "name": "Forecast",
            "path": "/path/to/forecast-{yyyymmdd}-{hh}-{fh:03}.nc",
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
def da_with_leadtime() -> xr.DataArray:
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
def da_with_validtime() -> xr.DataArray:
    one = np.array([1], dtype="float32")
    return xr.DataArray(
        name="HGT",
        data=one.reshape((1, 1, 1, 1, 1)),
        dims=["latitude", "longitude", "level", "time", "validtime"],
        coords=dict(
            latitude=(["latitude", "longitude"], one.reshape((1, 1))),
            longitude=(["latitude", "longitude"], one.reshape((1, 1))),
            level=(["level"], np.array([900], dtype="float32")),
            time=np.array([0], dtype="datetime64[ns]"),
            validtime=np.array([0], dtype="datetime64[ns]"),
        ),
    )


@fixture
def fakefs(fs):
    return Path(fs.create_dir("/test").path)


@fixture
def gen_config():
    def gen_config(config_data, rootpath) -> Config:
        dirs = ("grids/baseline", "grids/forecast", "run")
        grids_baseline, grids_forecast, run = [rootpath / x for x in dirs]
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

    return gen_config


@fixture
def logged(caplog):
    def logged(s: str):
        found = any(re.match(rf"^.*{s}.*$", message) for message in caplog.messages)
        caplog.clear()
        return found

    return logged


@fixture
def tc(da_with_leadtime):
    cycle = datetime.fromtimestamp(int(da_with_leadtime.time.values[0]), tz=timezone.utc)
    leadtime = timedelta(hours=int(da_with_leadtime.lead_time.values[0]))
    return times.TimeCoords(cycle=cycle, leadtime=leadtime)


@fixture
def utc():
    def utc(*args, **kwargs) -> datetime:
        # See https://github.com/python/mypy/issues/6799
        dt = datetime(*args, **kwargs, tzinfo=timezone.utc)  # type: ignore[misc]
        return dt.replace(tzinfo=None)

    return utc
