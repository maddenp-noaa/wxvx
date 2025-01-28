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


@external
def existing(path: Path):
    yield "Existing path %s" % path
    yield asset(path, path.exists)


@task
def forecast_dataset(forecast: Path):
    taskname = "Forecast %s" % forecast
    fd = xr.Dataset()
    yield taskname
    yield asset(fd, lambda: bool(fd))
    yield existing(path=forecast)
    logging.info("%s: Opening forecast %s", taskname, forecast)
    with catch_warnings():
        simplefilter("ignore")
        fd.update(xr.open_dataset(forecast))


@task
def forecast_var(var: Var, validtime: TimeCoords, forecast: Path, rundir: Path):
    fn = "%s.forecast.nc" % var
    path = rundir / "forecast" / validtime.yyyymmdd / validtime.hh / fn
    fd = forecast_dataset(forecast=forecast)
    yield "Forecast variable %s at %s" % (var, validtime)
    yield asset(path, path.is_file)
    yield fd
    da = refs(fd)[GFSVar.gfsvar(var.name)].sel(time=validtime.dt)
    # _set_cf_metadata(ds, taskname)
    path.parent.mkdir(parents=True, exist_ok=True)
    da.to_netcdf(path=path)


@task
def grib_message(var: Var, variables: set[Var], validtime: TimeCoords, rundir: Path, url: str):
    fn = "%s.baseline.grib2" % var
    path = rundir / "baseline" / validtime.yyyymmdd / validtime.hh / fn
    ts = validtime.dt.isoformat()
    taskname = "%s GRIB message %s" % (ts, var)
    idxdata = grib_index_data(
        variables=variables, validtime=validtime, rundir=rundir, url=f"{url}.idx", ts=ts
    )
    yield taskname
    yield asset(path, path.is_file)
    yield idxdata
    var_idxdata = refs(idxdata)[str(var)]
    fb, lb = var_idxdata.firstbyte, var_idxdata.lastbyte
    headers = {"Range": "bytes=%s" % (f"{fb}-{lb}" if lb else fb)}
    fetch(taskname=taskname, url=url, path=path, headers=headers)


@task
def grib_index_data(variables: set[Var], validtime: TimeCoords, rundir: Path, url: str, ts: str):
    idxdata: dict[str, GFSVar] = {}
    idxfile = grib_index_local(validtime=validtime, rundir=rundir, url=url, ts=ts)
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
def grib_index_local(validtime: TimeCoords, rundir: Path, url: str, ts):
    taskname = "%s GRIB index local" % ts
    path = rundir / "baseline" / validtime.yyyymmdd / validtime.hh / Path(urlparse(url).path).name
    yield taskname
    yield asset(path, path.is_file)
    yield grib_index_remote(url=url, ts=ts)
    fetch(taskname=taskname, url=url, path=path)


@external
def grib_index_remote(url: str, ts: str):
    yield "%s GRIB index remote %s" % (ts, url)
    yield asset(url, lambda: status(url) == 200)


@tasks
def verify_all(config: dict):
    taskname = "Verification"
    variables = set()
    for var in config["variables"]:
        levels = var.get("levels", [None])
        for level in levels:
            variables.add(Var(name=var["name"], levtype=var["levtype"], level=level))
    var_validtime_pairs = []
    for validtime in validtimes(cycles=config["cycles"], leadtimes=config["leadtimes"]):
        for var in sorted(list(variables))[:2]:
            var_validtime_pairs.append(
                verify_one(
                    forecast=Path(config["forecast"]),
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
    forecast: Path,
    var: Var,
    variables: set[Var],
    validtime: TimeCoords,
    rundir: Path,
    baseline: str,
):
    url = baseline.format(yyyymmdd=validtime.yyyymmdd, hh=validtime.hh)
    fv = forecast_var(var=var, validtime=validtime, forecast=forecast, rundir=rundir)
    gm = grib_message(var=var, variables=variables, validtime=validtime, rundir=rundir, url=url)
    yield "Verification of %s at %s" % (var, validtime)
    yield [fv, gm]
