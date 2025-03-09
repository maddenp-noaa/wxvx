from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

import netCDF4  # noqa: F401 # import before xarray cf. https://github.com/pydata/xarray/issues/7259
import numpy as np
import xarray as xr

from wxvx.types import VarMeta
from wxvx.util import WXVXError

if TYPE_CHECKING:  # pragma: no cover
    from wxvx.times import TimeCoords
    from wxvx.types import Config

UNKNOWN = "unknown"


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


def ds_from_da(c: Config, da: xr.DataArray, taskname: str) -> xr.Dataset:
    logging.info("%s: Setting CF metadata on %s", taskname, da.name)
    da["forecast_reference_time"].attrs["standard_name"] = "forecast_reference_time"
    da["time"].attrs["standard_name"] = "time"
    for name, standard_name, units in (
        ["latitude", "latitude", "degrees_north"],
        ["longitude", "longitude", "degrees_east"],
        ["level", "air_pressure", "hPa"],
    ):
        if hasattr(da, name):
            updates = {"standard_name": standard_name, "units": units}
            da[name].attrs.update(updates)
    meta = VARMETA[c.variables[da.name]["name"]]
    updates = {
        "grid_mapping_name": "latitude_longitude",
        "standard_name": meta.cf_standard_name,
        "units": meta.units,
    }
    da.attrs.update(updates)
    ds = da.to_dataset()
    ds.attrs["Conventions"] = "CF-1.8"
    return ds


def metlevel(level_type: str, level: float | None) -> str:
    try:
        prefix = {
            "atmosphere": "L",
            "heightAboveGround": "Z",
            "isobaricInhPa": "P",
        }[level_type]
    except KeyError as e:
        raise WXVXError("No MET level defined for level type %s" % level_type) from e
    return f"{prefix}%03d" % int(level or 0)


def _levelstr2num(levelstr: str) -> float | int:
    try:
        return int(levelstr)
    except ValueError:
        return float(levelstr)


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
