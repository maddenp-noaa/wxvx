from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import numpy as np
import xarray as xr
from pytest import fixture

from wxvx.types import Config


@fixture
def check_cf_metadata() -> Callable:
    def check(ds: xr.DataArray, name: str) -> None:
        assert ds.attrs["Conventions"] == "CF-1.8"
        da = ds[name]
        for k, v in [("standard_name", "geopotential_height"), ("units", "m")]:
            assert da.attrs[k] == v
        for k, v in [("standard_name", "latitude"), ("units", "degrees_north")]:
            assert da.latitude.attrs[k] == v
        assert da.init_time.attrs["standard_name"] == "forecast_reference_time"
        assert da.valid_time.attrs["standard_name"] == "time"

    return check


@fixture
def c(config_data, fakefs):
    return Config({**config_data, "workdir": str(fakefs)})


@fixture
def c_real(config_data, tmp_path):
    return Config({**config_data, "workdir": str(tmp_path)})


@fixture
def config_data():
    return {
        "baseline": {
            "name": "Baseline",
            "template": "https://some.url/path/to/a.grib2",
        },
        "cycles": {
            "start": "2024-12-19T18:00:00",
            "step": "12:00:00",
            "stop": "2024-12-20T06:00:00",
        },
        "forecast": {
            "name": "Forecast",
            "path": "/path/to/forecast",
        },
        "leadtimes": {
            "start": "00:00:00",
            "step": "06:00:00",
            "stop": "12:00:00",
        },
        "plot": {
            "baseline": True,
        },
        "threads": 4,
        "variables": {
            "REFC": {
                "level_type": "atmosphere",
                "stdname": "refc",
            },
            "SPFH": {
                "level_type": "isobaricInhPa",
                "levels": [1000],
                "stdname": "q",
            },
            "T2M": {
                "level_type": "heightAboveGround",
                "levels": [2],
                "stdname": "2t",
            },
        },
        "workdir": "/path/to/workdir",
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
            level=(["level"], np.array([1000], dtype="float32")),
            time=np.array([0], dtype="datetime64[ns]"),
            lead_time=np.array([0], dtype="timedelta64[ns]"),
        ),
    )


@fixture
def fakefs(fs):
    return Path(fs.create_dir("/test").path)


@fixture
def utc():
    def datetime_utc(*args, **kwargs) -> datetime:
        # See https://github.com/python/mypy/issues/6799
        dt = datetime(*args, **kwargs, tzinfo=timezone.utc)  # type: ignore[misc]
        return dt.replace(tzinfo=None)

    return datetime_utc
