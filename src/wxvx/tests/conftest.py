import numpy as np
import xarray as xr
from pytest import fixture

# pylint: disable=redefined-outer-name


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
        "baseline": "https://some.url/{yyyymmdd}/{hh}/a.grib2",
        "cycles": {
            "start": "2024-12-19T18:00:00",
            "step": "12:00:00",
            "stop": "2024-12-20T06:00:00",
        },
        "forecast": "/path/to/forecast.zarr",
        "leadtimes": {
            "start": "00:00:00",
            "step": "06:00:00",
            "stop": "12:00:00",
        },
        "rundir": "/path/to/run",
        "threads": 1,
        "variables": [
            {"levels": [1000], "levtype": "isobaricInhPa", "name": "gh"},
            {"levtype": "surface", "name": "t"},
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
