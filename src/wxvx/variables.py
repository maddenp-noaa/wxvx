from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

import netCDF4  # noqa: F401 # import before xarray cf. https://github.com/pydata/xarray/issues/7259

from wxvx.util import WXVXError

if TYPE_CHECKING:
    import xarray as xr  # pragma: no cover

UNKNOWN = "unknown"


class Var:
    """
    A generic variable.
    """

    def __init__(self, name: str, levtype: str, level: float | None = None):
        self.name = name
        self.levtype = levtype
        self.level = level
        self._keys = {"name", "levtype", "level"} if self.level is not None else {"name", "levtype"}

    def __eq__(self, other):
        return hash(self) == hash(other)

    def __hash__(self):
        return hash((self.name, self.levtype, self.level))

    def __lt__(self, other):
        return str(self) < str(other)

    def __repr__(self):
        keys = sorted(self._keys)
        vals = [f"{k}='{v}'" for k, v in zip(keys, [getattr(self, key) for key in keys])]
        return "%s(%s)" % (self.__class__.__name__, ", ".join(vals))

    def __str__(self):
        level = f"{self.level:04}" if self.level is not None else None
        vals = filter(None, [self.name, self.levtype, level])
        return "-".join(vals)


class HRRRVar(Var):
    """
    A HRRR variable.
    """

    def __init__(self, name: str, levstr: str, firstbyte: int, lastbyte: int):
        levtype, level = self._levinfo(levstr=levstr)
        name = self._stdname(name=name, levtype=levtype)
        super().__init__(name=name, levtype=levtype, level=level)
        self.firstbyte: int = firstbyte
        self.lastbyte: int | None = lastbyte if lastbyte > -1 else None
        self._keys = (
            {"name", "levtype", "level", "firstbyte", "lastbyte"}
            if self.level is not None
            else {"name", "levtype", "firstbyte", "lastbyte"}
        )

    @staticmethod
    def metlevel(levtype: str, level: float | None) -> str:
        try:
            prefix = {
                "atmosphere": "L",
                "heightAboveGround": "Z",
                "isobaricInhPa": "P",
            }[levtype]
        except KeyError as e:
            raise WXVXError("No MET level defined for level type %s" % levtype) from e
        return f"{prefix}%03d" % int(level or 0)

    @staticmethod
    def varname(name: str, levtype: str) -> str:
        return {
            ("2t", "heightAboveGround"): "TMP",
            ("gh", "isobaricInhPa"): "HGT",
            ("q", "isobaricInhPa"): "SPFH",
            ("refc", "atmosphere"): "REFC",
            ("t", "isobaricInhPa"): "TMP",
            ("u", "isobaricInhPa"): "UGRD",
            ("v", "isobaricInhPa"): "VGRD",
            ("w", "isobaricInhPa"): "VVEL",
        }.get((name, levtype), UNKNOWN)

    @staticmethod
    def _level_pressure(levstr: str) -> float | int | None:
        if m := re.match(r"^([0-9\.]+) m above ground$", levstr):
            return _levelstr2num(m[1])
        if m := re.match(r"^([0-9\.]+) mb$", levstr):
            return _levelstr2num(m[1])
        return None

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

    @staticmethod
    def _stdname(name: str, levtype: str) -> str:
        return {
            ("HGT", "isobaricInhPa"): "gh",
            ("REFC", "atmosphere"): "refc",
            ("SPFH", "isobaricInhPa"): "q",
            ("TMP", "heightAboveGround"): "2t",  # too specific?
            ("TMP", "isobaricInhPa"): "t",
            ("TMP", "surface"): "t",
            ("UGRD", "isobaricInhPa"): "u",
            ("VGRD", "isobaricInhPa"): "v",
            ("VVEL", "isobaricInhPa"): "w",
        }.get((name, levtype), UNKNOWN)


def cf_compliant_dataset(da: xr.DataArray, taskname: str) -> xr.Dataset:
    logging.info("%s: Setting CF metadata on %s", taskname, da.name)
    for name, long_name, standard_name in [
        ("time", "Forecast Reference Time", "forecast_reference_time"),
    ]:
        updates = {"long_name": long_name, "standard_name": standard_name}
        logging.debug("%s: Setting %s on %s", taskname, updates, name)
        da[name].attrs.update(updates)
    for name, long_name, standard_name, units in (
        ["level", "pressure level", "air_pressure", "hPa"],
        ["latitude", "latitude", "latitude", "degrees_north"],
        ["longitude", "longitude", "longitude", "degrees_east"],
    ):
        if hasattr(da, name):
            updates = {"long_name": long_name, "standard_name": standard_name, "units": units}
            logging.debug("%s: Setting %s on %s", taskname, updates, name)
            da[name].attrs.update(updates)
    for name, long_name, standard_name in (
        ["HGT", "Geopotential Height", "geopotential_height"],
        ["REFC", "Composite Reflectivity", "unknown"],
        ["SPFH", "Specific Humidity", "specific_humidity"],
        ["T2M", "Temperature", "air_temperature"],
        ["TMP", "Temperature", "air_temperature"],
        ["UGRD", "U-Component of Wind", "eastward_wind"],
        ["VGRD", "V-Component of Wind", "northward_wind"],
        ["VVEL", "Vertical Velocity (Pressure),", "lagrangian_tendency_of_air_pressure"],
    ):
        updates = {
            "grid_mapping_name": "latitude_longitude",
            "long_name": long_name,
            "standard_name": standard_name,
            "units": forecast_var_units(name),
        }
        if da.name == name:
            logging.debug("%s: Setting %s on %s", taskname, updates, name)
            da.attrs.update(updates)
    ds = da.to_dataset()
    ds.attrs["Conventions"] = "CF-1.8"
    return ds


def forecast_var_units(name: str) -> str:
    return {
        "HGT": "m",
        "REFC": "dBZ",
        "SPFH": "1",
        "T2M": "K",
        "TMP": "K",
        "UGRD": "m s-1",
        "VGRD": "m s-1",
        "VVEL": "Pa s-1",
    }[name]


def _levelstr2num(levelstr: str) -> float | int:
    try:
        return int(levelstr)
    except ValueError:
        return float(levelstr)
