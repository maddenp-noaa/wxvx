import logging
from itertools import pairwise
from pathlib import Path
from urllib.parse import urlparse
from warnings import catch_warnings, simplefilter

import xarray as xr
from iotaa import asset, external, refs, task, tasks

from wxvx.net import fetch, status
from wxvx.time import TimeCoords, validtimes
from wxvx.vars import GFSVar, Var

# Tasks


@external
def exists(path: Path, taskname: str):
    yield taskname
    yield asset(path, path.exists)


@task
def grib_message(var: Var, variables: set[Var], tcoord: TimeCoords, rundir: Path, url: str):
    ts = tcoord.dt.isoformat()
    taskname = "%s GRIB message %s" % (ts, var)
    fn = "%s.baseline.grib2" % var
    path = rundir / tcoord.yyyymmdd / tcoord.hh / "000" / str(var) / fn
    idxdata = grib_index_data(
        variables=variables, tcoord=tcoord, rundir=rundir, url=f"{url}.idx", ts=ts
    )
    yield taskname
    yield asset(path, path.is_file)
    yield idxdata
    var_idxdata = refs(idxdata)[str(var)]
    fb, lb = var_idxdata.firstbyte, var_idxdata.lastbyte
    headers = {"Range": "bytes=%s" % (f"{fb}-{lb}" if lb else fb)}
    fetch(taskname=taskname, url=url, path=path, headers=headers)


@task
def grib_index_data(variables: set[Var], tcoord: TimeCoords, rundir: Path, url: str, ts: str):
    idxdata: dict[str, GFSVar] = {}
    idxfile = grib_index_local(tcoord=tcoord, rundir=rundir, url=url, ts=ts)
    yield "%s GRIB index data" % ts
    yield asset(idxdata, lambda: bool(idxdata))
    yield idxfile
    lines = refs(idxfile).read_text(encoding="utf-8").strip().split("\n")
    lines.append(":-1:::::")  # end marker
    for this_record, next_record in pairwise([line.split(":") for line in lines]):
        gfsvar = GFSVar(
            name=GFSVar.stdvar(this_record[3]),
            levstr=this_record[4],
            firstbyte=int(this_record[1]),
            lastbyte=int(next_record[1]) - 1,
        )
        if gfsvar in variables:
            idxdata[str(gfsvar)] = gfsvar


@task
def grib_index_local(tcoord: TimeCoords, rundir: Path, url: str, ts):
    taskname = "%s GRIB index local" % ts
    path = rundir / tcoord.yyyymmdd / tcoord.hh / Path(urlparse(url).path).name
    yield taskname
    yield asset(path, path.is_file)
    yield grib_index_remote(url=url, ts=ts)
    fetch(taskname=taskname, url=url, path=path)


@external
def grib_index_remote(url: str, ts: str):
    yield "%s GRIB index remote %s" % (ts, url)
    yield asset(url, lambda: status(url) == 200)


# @task
# def netcdf_file(forecast: Path, rundir: Path):
#     taskname = "Forecast netCDF file %s" % path
#     path = rundir / "forecast.nc"
#     yield taskname
#     yield asset(path, path.is_file)
#     yield exists(path=forecast, taskname="Forecast %s" % forecast)
#     logging.info("%s: Opening forecast %s", taskname, forecast)
#     with catch_warnings():
#         simplefilter("ignore")
#         ds = xr.open_dataset(forecast)
#     _set_cf_metadata(ds, taskname)
#     logging.info("Writing forecast to %s", path)
#     path.parent.mkdir(parents=True, exist_ok=True)
#     # ds.to_netcdf(path=path)
#     path.touch()


# @tasks
# def run_directory(config: dict):
#     keys = ("baseline", "cycles", "forecast", "leadtimes", "rundir", "variables")
#     baseline, cycles, forecast, leadtimes, rundir, variables = [config[k] for k in keys]
#     yield "Run directory %s" % rundir
#     yield [
#         grib_messages(
#             baseline=baseline,
#             cycles=cycles,
#             leadtimes=leadtimes,
#             rundir=Path(rundir),
#             variables=variables,
#         ),
#         netcdf_file(forecast=Path(forecast), rundir=Path(rundir)),
#     ]


@tasks
def verify_all(config: dict):
    taskname = "Verification"
    logging.info("%s: Opening forecast %s", taskname, config["forecast"])
    with catch_warnings():
        simplefilter("ignore")
        ds = xr.open_dataset(config["forecast"])  # PM factor out to task with external req
    _set_cf_metadata(ds, taskname)
    variables = _variables(needed=config["variables"])
    var_validtime_pairs = []
    for validtime in validtimes(cycles=config["cycles"], leadtimes=config["leadtimes"]):
        for var in sorted(list(variables))[:2]:
            var_validtime_pairs.append(
                verify_one(
                    var=var,
                    variables=variables,
                    validtime=validtime,
                    rundir=Path(config["rundir"]),
                    baseline=config["baseline"],
                )
            )
    yield taskname
    yield var_validtime_pairs


@tasks  # PM change to @task
def verify_one(
    var: Var,
    variables: set[Var],
    validtime: TimeCoords,
    rundir: Path,
    baseline: str,
):
    url = baseline.format(yyyymmdd=validtime.yyyymmdd, hh=validtime.hh)
    gm = grib_message(var=var, variables=variables, tcoord=validtime, rundir=rundir, url=url)
    yield "Verification of %s at %s" % (var, validtime)
    yield gm


# Helpers


def _set_cf_metadata(ds: xr.Dataset, taskname: str) -> None:  # PM drive per req'd var
    logging.info("%s: Setting CF metadata on dataset", taskname)
    ds.attrs["Conventions"] = "CF-1.8"
    ds["latitude_longitude"] = int()
    ds.latitude_longitude.attrs["grid_mapping_name"] = "latitude_longitude"
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
        logging.debug("%s: Setting %s on %s", taskname, updates, var)
        ds[var].attrs.update(updates)
    for var, long_name, standard_name, units in (
        ["latitude", "latitude", "latitude", "degrees_north"],
        ["level", "pressure level", "air_pressure", "hPa"],
        ["longitude", "longitude", "longitude", "degrees_east"],
    ):
        updates = {"long_name": long_name, "standard_name": standard_name, "units": units}
        logging.debug("%s: Setting %s on %s", taskname, updates, var)
        ds[var].attrs.update(updates)
    for var, long_name, standard_name in (
        ["lead_time", "Forecast Period", "forecast_period"],
        ["time", "Forecast Reference Time", "forecast_reference_time"],
    ):
        updates = {"long_name": long_name, "standard_name": standard_name}
        logging.debug("%s: Setting %s on %s", taskname, updates, var)
        ds[var].attrs.update(updates)


def _variables(needed: list[dict]) -> set[Var]:
    variables = set()
    for var in needed:
        levels = var.get("levels", [None])
        for level in levels:
            variables.add(Var(name=var["name"], levtype=var["levtype"], level=level))
    return variables
