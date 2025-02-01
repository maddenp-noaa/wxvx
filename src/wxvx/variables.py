from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import xarray as xr  # pragma: no cover


GFS2STD = {
    "HGT": "gh",
    "REFC": "refc",
    "SPFH": "q",
    "T2M": "t",
    "TMP": "t",
    "UGRD": "u",
    "VGRD": "v",
    "VVEL": "w",
}

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
        return hash((self._stdname, self.levtype, self.level))

    def __lt__(self, other):
        return str(self) < str(other)

    def __repr__(self):
        keys = sorted(self._keys)
        vals = [f"{k}='{v}'" for k, v in zip(keys, [getattr(self, key) for key in keys])]
        return "%s(%s)" % (self.__class__.__name__, ", ".join(vals))

    def __str__(self):
        level = f"{self.level:04}" if self.level is not None else None
        vals = filter(None, [self._stdname, self.levtype, level])
        return "-".join(vals)

    @property
    def _stdname(self) -> str:
        return self.name


class GFSVar(Var):
    """
    A GFS-style variable.
    """

    def __init__(self, name: str, levstr: str, firstbyte: int, lastbyte: int):
        levtype, level = self._levinfo(levstr)
        super().__init__(name=name, levtype=levtype, level=level)
        self.firstbyte: int = firstbyte
        self.lastbyte: int | None = lastbyte if lastbyte > -1 else None
        self._keys = (
            {"name", "levtype", "level", "firstbyte", "lastbyte"}
            if self.level is not None
            else {"name", "levtype", "firstbyte", "lastbyte"}
        )

    @classmethod
    def gfsvar(cls, name: str) -> str:
        return {v: k for k, v in GFS2STD.items()}.get(name, UNKNOWN)

    @classmethod
    def stdvar(cls, name: str) -> str:
        return GFS2STD.get(name, UNKNOWN)

    @staticmethod
    def _level_pressure(levstr: str) -> float | int | None:
        if m := re.match(r"^([0-9\.]+) mb$", levstr):
            return _levelstr2num(m[1])
        return None

    @staticmethod
    def _levinfo(levstr: str) -> tuple[str, float | int | None]:
        if m := re.match(r"^entire atmosphere$", levstr):
            return ("atmosphere", None)
        if m := re.match(r"^(\d+(\.\d+)?) mb$", levstr):
            return ("isobaricInhPa", _levelstr2num(m[1]))
        if m := re.match(r"^surface$", levstr):
            return ("surface", None)
        return (UNKNOWN, None)

    @property
    def _stdname(self) -> str:
        return self.stdvar(self.name)


def set_cf_metadata(da: xr.DataArray, taskname: str) -> None:
    logging.info("%s: Setting CF metadata on %s", taskname, da.name)
    da.attrs["Conventions"] = "CF-1.8"
    da["latitude_longitude"] = 0
    da.latitude_longitude.attrs["grid_mapping_name"] = "latitude_longitude"
    for name, long_name, standard_name, units in (
        ["HGT", "Geopotential Height", "geopotential_height", "m"],
        ["REFC", "Composite Reflectivity", "unknown", "dBZ"],
        ["SPFH", "Specific Humidity", "specific_humidity", "1"],
        ["T2M", "Temperature", "surface_temperature", "K"],
        ["TMP", "Temperature", "air_temperature", "K"],
        ["UGRD", "U-Component of Wind", "eastward_wind", "m s-1"],
        ["VGRD", "V-Component of Wind", "northward_wind", "m s-1"],
        ["VVEL", "Vertical Velocity (Pressure],", "lagrangian_tendency_of_air_pressure", "Pa s-1"],
    ):
        updates = {
            "grid_mapping": "latitude_longitude",
            "long_name": long_name,
            "standard_name": standard_name,
            "units": units,
        }
        if da.name == name:
            logging.debug("%s: Setting %s on %s", taskname, updates, name)
            da.attrs.update(updates)
    for name, long_name, standard_name, units in (
        ["latitude", "latitude", "latitude", "degrees_north"],
        ["level", "pressure level", "air_pressure", "hPa"],
        ["longitude", "longitude", "longitude", "degrees_east"],
    ):
        if hasattr(da, name):
            updates = {"long_name": long_name, "standard_name": standard_name, "units": units}
            logging.debug("%s: Setting %s on %s", taskname, updates, name)
            da[name].attrs.update(updates)
    for name, long_name, standard_name in (
        ["lead_time", "Forecast Period", "forecast_period"],
        ["time", "Forecast Reference Time", "forecast_reference_time"],
    ):
        updates = {"long_name": long_name, "standard_name": standard_name}
        logging.debug("%s: Setting %s on %s", taskname, updates, name)
        da[name].attrs.update(updates)


def _levelstr2num(levelstr: str) -> float | int:
    try:
        return int(levelstr)
    except ValueError:
        return float(levelstr)
