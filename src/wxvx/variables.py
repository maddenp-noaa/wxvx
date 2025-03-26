from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Literal

import netCDF4  # noqa: F401 # import before xarray cf. https://github.com/pydata/xarray/issues/7259
import numpy as np
import xarray as xr
from pyproj import Proj

from wxvx.types import VarMeta
from wxvx.util import WXVXError

if TYPE_CHECKING:  # pragma: no cover
    from wxvx.times import TimeCoords
    from wxvx.types import Config

# Public

UNKNOWN = "unknown"


VARMETA = {
    x.name: x
    for x in [
        VarMeta(
            cf_standard_name="air_temperature",
            description="2m Temperature",
            level_type="heightAboveGround",
            met_linetype="cnt",
            met_stat="RMSE",
            name="2t",
            units="K",
        ),
        VarMeta(
            cf_standard_name="geopotential_height",
            description="Geopotential Height at {level} mb",
            level_type="isobaricInhPa",
            met_linetype="cnt",
            met_stat="RMSE",
            name="gh",
            units="m",
        ),
        VarMeta(
            cf_standard_name="specific_humidity",
            description="Specific Humidity at {level} mb",
            level_type="isobaricInhPa",
            met_linetype="cnt",
            met_stat="RMSE",
            name="q",
            units="1",
        ),
        VarMeta(
            cf_standard_name="unknown",
            description="Composite Reflectivity",
            level_type="atmosphere",
            met_linetype="cts",
            met_stat="PODY",
            name="refc",
            units="dBZ",
        ),
        VarMeta(
            cf_standard_name="air_temperature",
            description="Temperature at {level} mb",
            level_type="isobaricInhPa",
            met_linetype="cnt",
            met_stat="RMSE",
            name="t",
            units="K",
        ),
        VarMeta(
            cf_standard_name="eastward_wind",
            description="U-Component of Wind at {level} mb",
            level_type="isobaricInhPa",
            met_linetype="cnt",
            met_stat="RMSE",
            name="u",
            units="m s-1",
        ),
        VarMeta(
            cf_standard_name="northward_wind",
            description="V-Component of Wind at {level} mb",
            level_type="isobaricInhPa",
            met_linetype="cnt",
            met_stat="RMSE",
            name="v",
            units="m s-1",
        ),
        VarMeta(
            cf_standard_name="lagrangian_tendency_of_air_pressure",
            description="Vertical Velocity at {level} mb",
            level_type="isobaricInhPa",
            met_linetype="cnt",
            met_stat="RMSE",
            name="w",
            units="Pa s-1",
        ),
    ]
}


class Var:
    """
    A generic variable.
    """

    def __init__(self, name: str, level_type: str, level: float | None = None):
        self.name = name
        self.level_type = level_type
        self.level = level
        self._keys = (
            {"name", "level_type", "level"} if self.level is not None else {"name", "level_type"}
        )

    def __eq__(self, other):
        return hash(self) == hash(other)

    def __hash__(self):
        return hash((self.name, self.level_type, self.level))

    def __lt__(self, other):
        return str(self) < str(other)

    def __repr__(self):
        keys = sorted(self._keys)
        vals = [
            f"{k}='{v}'" if isinstance(v, str) else f"{k}={v}"
            for k, v in zip(keys, [getattr(self, key) for key in keys])
        ]
        return "%s(%s)" % (self.__class__.__name__, ", ".join(vals))

    def __str__(self):
        level = f"{self.level:04}" if self.level is not None else None
        vals = filter(None, [self.name, self.level_type, level])
        return "-".join(vals)


class HRRR(Var):
    """
    A HRRR variable.
    """

    proj = Proj(
        {
            "a": 6371229,
            "b": 6371229,
            "lat_0": 38.5,
            "lat_1": 38.5,
            "lat_2": 38.5,
            "lon_0": 262.5,
            "proj": "lcc",
        }
    )

    def __init__(self, name: str, levstr: str, firstbyte: int, lastbyte: int):
        level_type, level = self._levinfo(levstr=levstr)
        name = self._canonicalize(name=name, level_type=level_type)
        super().__init__(name=name, level_type=level_type, level=level)
        self.firstbyte: int = firstbyte
        self.lastbyte: int | None = lastbyte if lastbyte > -1 else None
        self._keys = (
            {"name", "level_type", "level", "firstbyte", "lastbyte"}
            if self.level is not None
            else {"name", "level_type", "firstbyte", "lastbyte"}
        )

    @staticmethod
    def varname(name: str) -> str:
        return {
            "2t": "TMP",
            "gh": "HGT",
            "q": "SPFH",
            "refc": "REFC",
            "t": "TMP",
            "u": "UGRD",
            "v": "VGRD",
            "w": "VVEL",
        }.get(name, UNKNOWN)

    @staticmethod
    def _canonicalize(name: str, level_type: str) -> str:
        return {
            ("HGT", "isobaricInhPa"): "gh",
            ("REFC", "atmosphere"): "refc",
            ("SPFH", "isobaricInhPa"): "q",
            ("TMP", "heightAboveGround"): "2t",
            ("TMP", "isobaricInhPa"): "t",
            ("UGRD", "isobaricInhPa"): "u",
            ("VGRD", "isobaricInhPa"): "v",
            ("VVEL", "isobaricInhPa"): "w",
        }.get((name, level_type), UNKNOWN)

    @staticmethod
    def _levinfo(levstr: str) -> tuple[str, float | int | None]:
        if m := re.match(r"^entire atmosphere$", levstr):
            return ("atmosphere", None)
        if m := re.match(r"^(\d+(\.\d+)?) m above ground$", levstr):
            return ("heightAboveGround", _levelstr2num(m[1]))
        if m := re.match(r"^(\d+(\.\d+)?) mb$", levstr):
            return ("isobaricInhPa", _levelstr2num(m[1]))
        if m := re.match(r"^surface$", levstr):
            return ("surface", None)
        return (UNKNOWN, None)


def da_construct(src: xr.DataArray) -> xr.DataArray:
    return xr.DataArray(
        data=src.expand_dims(dim=["forecast_reference_time", "time"]),
        coords=dict(
            forecast_reference_time=[src.time.values + np.timedelta64(0, "s")],
            time=[src.time.values + src.lead_time.values],
            latitude=src.latitude,
            longitude=src.longitude,
        ),
        dims=("forecast_reference_time", "time", "latitude", "longitude"),
        name=src.name,
    )


def da_select(ds: xr.Dataset, c: Config, varname: str, tc: TimeCoords, var: Var) -> xr.DataArray:
    try:
        da = (
            ds[varname]
            .sel(time=np.datetime64(str(tc.cycle.isoformat())))
            .sel(lead_time=np.timedelta64(int(tc.leadtime.total_seconds()), "s"))
        )
        if var.level is not None and hasattr(da, "level"):
            da = da.sel(level=var.level)
    except KeyError as e:
        msg = "Variable %s valid at %s not found in %s" % (varname, tc, c.forecast.path)
        raise WXVXError(msg) from e
    return da


def ds_construct(c: Config, da: xr.DataArray, taskname: str) -> xr.Dataset:
    logging.info("%s: Creating CF-compliant %s dataset", taskname, da.name)
    assert len(da.shape) == 4
    proj = Proj(c.forecast.projection)
    latlon = proj.name == "longlat"  # yes, "longlat"
    dims = ["forecast_reference_time", "time"]
    dims.extend(["latitude", "longitude"] if latlon else ["y", "x"])
    crs = "CRS"
    meta = VARMETA[c.variables[da.name]["name"]]
    attrs = dict(grid_mapping=crs, standard_name=meta.cf_standard_name, units=meta.units)
    dims_lat, dims_lon = ([k] if latlon else ["y", "x"] for k in ["latitude", "longitude"])
    coords = {
        "forecast_reference_time": _da_to_forecast_reference_time(da),
        "time": _da_to_time(da),
        "latitude": _da_to_latitude(da, dims_lat),
        "longitude": _da_to_longitude(da, dims_lon),
    }
    if not latlon:
        coords = {**coords, "y": _da_to_y(da, proj), "x": _da_to_x(da, proj)}
    return xr.Dataset(
        data_vars={
            da.name: xr.DataArray(data=da.values, dims=dims, attrs=attrs),
            crs: _da_crs(proj),
        },
        coords=coords,
        attrs=dict(
            Conventions="CF-1.8",
            level=da.level.values[0] if hasattr(da, "level") else np.nan,
        ),
    )


def metlevel(level_type: str, level: float | None) -> str:
    try:
        prefix = {"atmosphere": "L", "heightAboveGround": "Z", "isobaricInhPa": "P"}[level_type]
    except KeyError as e:
        raise WXVXError("No MET level defined for level type %s" % level_type) from e
    return f"{prefix}%03d" % int(level or 0)


# Private


def _da_crs(proj: Proj) -> xr.DataArray:
    cf = proj.crs.to_cf()
    return xr.DataArray(
        data=0,
        attrs={
            k: cf[k]
            for k in [
                "false_easting",
                "false_northing",
                "grid_mapping_name",
                "latitude_of_projection_origin",
                "longitude_of_central_meridian",
                "standard_parallel",
            ]
            if k in cf
        },
    )


def _da_grid_coords(
    da: xr.DataArray, proj: Proj, k: Literal["latitude", "longitude"]
) -> np.ndarray:
    ks = ("latitude", "longitude")
    assert k in ks
    lats, lons = [da[k].values for k in ks]
    i1, i2 = {"latitude": (lambda n: (n, 0), 1), "longitude": (lambda n: (0, n), 0)}[k]
    return np.array([proj(lons[i1(n)], lats[i1(n)])[i2] for n in range(da.latitude.sizes[k])])


def _da_to_forecast_reference_time(da: xr.DataArray) -> xr.DataArray:
    var = da.forecast_reference_time
    return xr.DataArray(
        data=var.values,
        dims=["forecast_reference_time"],
        name=var.name,
        attrs=dict(standard_name="forecast_reference_time"),
    )


def _da_to_latitude(da: xr.DataArray, dims: list[str]) -> xr.DataArray:
    var = da.latitude
    return xr.DataArray(
        data=var.values,
        dims=dims,
        name=var.name,
        attrs=dict(standard_name="latitude", units="degrees_north"),
    )


def _da_to_longitude(da: xr.DataArray, dims=list[str]) -> xr.DataArray:
    var = da.longitude
    return xr.DataArray(
        data=var.values,
        dims=dims,
        name=var.name,
        attrs=dict(standard_name="longitude", units="degrees_east"),
    )


def _da_to_time(da: xr.DataArray) -> xr.DataArray:
    var = da.time
    return xr.DataArray(
        data=var.values, dims=["time"], name=var.name, attrs=dict(standard_name="time")
    )


def _da_to_x(da: xr.DataArray, proj: Proj) -> xr.DataArray:
    return xr.DataArray(
        data=_da_grid_coords(da, proj, "longitude"),
        dims=["x"],
        attrs=dict(standard_name="projection_x_coordinate", units="m"),
    )


def _da_to_y(da: xr.DataArray, proj: Proj) -> xr.DataArray:
    return xr.DataArray(
        data=_da_grid_coords(da, proj, "latitude"),
        dims=["y"],
        attrs=dict(standard_name="projection_y_coordinate", units="m"),
    )


def _levelstr2num(levelstr: str) -> float | int:
    try:
        return int(levelstr)
    except ValueError:
        return float(levelstr)
