import logging
import re
from typing import Optional

import xarray as xr

UNKNOWN = "unknown"


class Var:

    def __init__(self, name: str, levtype: str, level: Optional[str] = None):
        self.name = name
        self.levtype = levtype
        self.level = str(level) if level else None
        self._keys = ["name", "levtype", "level"] if self.level else ["name", "levtype"]

    def __eq__(self, other):
        return hash(self) == hash(other)

    def __hash__(self):
        return hash((self.name, self.levtype, self.level))

    def __lt__(self, other):
        return str(self) < str(other)

    def __repr__(self):
        vals = [f"{k}={v}" for k, v in zip(self._keys, [getattr(self, key) for key in self._keys])]
        return "%s(%s)" % (self.__class__.__name__, ", ".join(vals))

    def __str__(self):
        level = f"{int(self.level):04}" if self.level else None
        vals = filter(None, [self.name, self.levtype, level])
        return "-".join(vals)


class GFSVar(Var):

    def __init__(self, name: str, levstr: str, firstbyte: int, lastbyte: int):
        levtype, level = self._levinfo(levstr)
        super().__init__(name=name, levtype=levtype, level=level)
        self.firstbyte: int = firstbyte
        self.lastbyte: Optional[int] = lastbyte if lastbyte > 0 else None
        self._keys = (
            ["name", "levtype", "level", "firstbyte", "lastbyte"]
            if self.level
            else ["name", "levtype", "firstbyte", "lastbyte"]
        )

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

    STD2GFS = {v: k for k, v in GFS2STD.items()}

    @classmethod
    def gfsvar(cls, name: str) -> str:
        return cls.STD2GFS.get(name, UNKNOWN)

    @classmethod
    def stdvar(cls, name: str) -> str:
        return cls.GFS2STD.get(name, UNKNOWN)

    @staticmethod
    def _level_pressure(levstr: str) -> Optional[str]:
        return m[1] if (m := re.match(r"^([0-9\.]+) mb$", levstr)) else None

    @staticmethod
    def _levinfo(levstr: str) -> tuple[str, Optional[str]]:
        if m := re.match(r"^entire atmosphere$", levstr):
            return ("atmosphere", None)
        if m := re.match(r"^(\d+(\.\d+)?) mb$", levstr):
            return ("isobaricInhPa", m[1])
        if m := re.match(r"^surface$", levstr):
            return ("surface", None)
        return (UNKNOWN, None)


def set_cf_metadata(da: xr.DataArray, taskname: str) -> None:
    logging.info("%s: Setting CF metadata on %s", taskname, da.name)
    da.attrs["Conventions"] = "CF-1.8"
    da["latitude_longitude"] = int()
    da.latitude_longitude.attrs["grid_mapping_name"] = "latitude_longitude"
    for var, long_name, standard_name, units in (
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
        if da.name == var:
            logging.debug("%s: Setting %s on %s", taskname, updates, var)
            da.attrs.update(updates)
    for var, long_name, standard_name, units in (
        ["latitude", "latitude", "latitude", "degrees_north"],
        ["level", "pressure level", "air_pressure", "hPa"],
        ["longitude", "longitude", "longitude", "degrees_east"],
    ):
        updates = {"long_name": long_name, "standard_name": standard_name, "units": units}
        logging.debug("%s: Setting %s on %s", taskname, updates, var)
        da[var].attrs.update(updates)
    for var, long_name, standard_name in (
        ["lead_time", "Forecast Period", "forecast_period"],
        ["time", "Forecast Reference Time", "forecast_reference_time"],
    ):
        updates = {"long_name": long_name, "standard_name": standard_name}
        logging.debug("%s: Setting %s on %s", taskname, updates, var)
        da[var].attrs.update(updates)
