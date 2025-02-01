from datetime import datetime, timezone

import numpy as np
import xarray as xr
from pytest import fixture


@fixture
def check_cf_metadata():
    def check(da: xr.DataArray):
        for k, v in [
            ("Conventions", "CF-1.8"),
            ("grid_mapping", "latitude_longitude"),
            ("long_name", "Geopotential Height"),
            ("standard_name", "geopotential_height"),
            ("units", "m"),
        ]:
            assert da.attrs[k] == v
        for k, v in [
            ("long_name", "latitude"),
            ("standard_name", "latitude"),
            ("units", "degrees_north"),
        ]:
            assert da.latitude.attrs[k] == v
        for k, v in [
            ("long_name", "pressure level"),
            ("standard_name", "air_pressure"),
            ("units", "hPa"),
        ]:
            assert da.level.attrs[k] == v
        for k, v in [
            ("long_name", "longitude"),
            ("standard_name", "longitude"),
            ("units", "degrees_east"),
        ]:
            assert da.longitude.attrs[k] == v
        for k, v in [("long_name", "Forecast Period"), ("standard_name", "forecast_period")]:
            assert da.lead_time.attrs[k] == v
        for k, v in [
            ("long_name", "Forecast Reference Time"),
            ("standard_name", "forecast_reference_time"),
        ]:
            assert da.time.attrs[k] == v

    return check


@fixture
def config():
    return {
        "baseline": "/".join(
            [
                "https://noaa-hrrr-bdp-pds.s3.amazonaws.com",
                "hrrr.{yyyymmdd}",
                "conus",
                "hrrr.t{hh}z.wrfprsf{ff}.grib2",
            ]
        ),
        "cycles": {
            "start": "2024-12-19T18:00:00",
            "step": "12:00:00",
            "stop": "2024-12-20T06:00:00",
        },
        "forecast": "/path/to/forecast",
        "leadtimes": {
            "start": "00:00:00",
            "step": "06:00:00",
            "stop": "12:00:00",
        },
        "rundir": "/path/to/rundir",
        "threads": 4,
        "variables": [
            {"name": "q", "levtype": "isobaricInhPa", "levels": [1000]},
            {"name": "refc", "levtype": "atmosphere"},
            {"name": "t", "levtype": "surface"},
        ],
    }


@fixture
def da() -> xr.DataArray:
    return xr.DataArray(
        name="HGT",
        data=np.zeros((1, 1, 1, 1, 1)),
        dims=["latitude", "longitude", "level", "time", "lead_time"],
        coords=dict(
            latitude=(["latitude", "longitude"], np.zeros((1, 1))),
            longitude=(["latitude", "longitude"], np.zeros((1, 1))),
            level=(["level"], np.array([1000])),
            time=np.zeros((1,)),
            lead_time=np.zeros((1,)),
        ),
    )


@fixture
def utc():
    def datetime_utc(*args, **kwargs) -> datetime:
        # See https://github.com/python/mypy/issues/6799
        dt = datetime(*args, **kwargs, tzinfo=timezone.utc)  # type: ignore[misc]
        return dt.replace(tzinfo=None)

    return datetime_utc
