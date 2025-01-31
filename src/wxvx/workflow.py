import logging
from itertools import pairwise
from pathlib import Path
from urllib.parse import urlparse
from warnings import catch_warnings, simplefilter

import numpy as np
import xarray as xr
from iotaa import asset, external, refs, task, tasks

from wxvx.net import fetch, status
from wxvx.time import TimeCoords, timecoords
from wxvx.variables import GFSVar, Var, set_cf_metadata


@external
def existing(path: Path):
    yield "Existing path %s" % path
    yield asset(path, path.exists)


@task
def forecast_dataset(forecast: Path):
    taskname = "Forecast %s" % forecast
    ds = xr.Dataset()
    yield taskname
    yield asset(ds, lambda: bool(ds))
    yield existing(path=forecast)
    logging.info("%s: Opening forecast %s", taskname, forecast)
    with catch_warnings():
        simplefilter("ignore")
        ds.update(xr.open_dataset(forecast))


@task
def forecast_var(var: Var, tc: TimeCoords, forecast: Path, rundir: Path):
    fn = "%s.forecast.nc" % var
    path = rundir / "forecast" / tc.yyyymmdd / tc.hh / fn
    taskname = "Forecast variable %s at %s" % (var, tc)
    fd = forecast_dataset(forecast=forecast)
    yield taskname
    yield asset(path, path.is_file)
    yield fd
    da = (
        refs(fd)[GFSVar.gfsvar(var.name)]
        .sel(time=np.datetime64(str(tc.cycle.iso)))
        .sel(lead_time=np.timedelta64(int(tc.leadtime.total_seconds()), "s"))
    )
    set_cf_metadata(da=da, taskname=taskname)
    path.parent.mkdir(parents=True, exist_ok=True)
    da.to_netcdf(path=path)


@task
def grib_message(var: Var, variables: set[Var], tc: TimeCoords, rundir: Path, url: str):
    fn = "%s.baseline.grib2" % var
    path = rundir / "baseline" / tc.yyyymmdd / tc.hh / fn
    ts = tc.validtime.isoformat()
    taskname = "%s GRIB message %s" % (ts, var)
    idxdata = grib_index_data(variables=variables, tc=tc, rundir=rundir, url=f"{url}.idx", ts=ts)
    yield taskname
    yield asset(path, path.is_file)
    yield idxdata
    var_idxdata = refs(idxdata)[str(var)]
    fb, lb = var_idxdata.firstbyte, var_idxdata.lastbyte
    headers = {"Range": "bytes=%s" % (f"{fb}-{lb}" if lb else fb)}
    fetch(taskname=taskname, url=url, path=path, headers=headers)


@task
def grib_index_data(variables: set[Var], tc: TimeCoords, rundir: Path, url: str, ts: str):
    idxdata: dict[str, GFSVar] = {}
    idxfile = grib_index_local(tc=tc, rundir=rundir, url=url, ts=ts)
    yield "%s GRIB index data" % ts
    yield asset(idxdata, lambda: bool(idxdata))
    yield idxfile
    lines = refs(idxfile).read_text(encoding="utf-8").strip().split("\n")
    lines.append(":-1:::::")  # end marker
    for this_record, next_record in pairwise([line.split(":") for line in lines]):
        gfsvar = GFSVar(
            name=this_record[3],
            levstr=this_record[4],
            firstbyte=int(this_record[1]),
            lastbyte=int(next_record[1]) - 1,
        )
        if gfsvar in variables:
            idxdata[str(gfsvar)] = gfsvar


@task
def grib_index_local(tc: TimeCoords, rundir: Path, url: str, ts: str):
    taskname = "%s GRIB index local" % ts
    path = rundir / "baseline" / tc.yyyymmdd / tc.hh / Path(urlparse(url).path).name
    yield taskname
    yield asset(path, path.is_file)
    yield grib_index_remote(url=url, ts=ts)
    fetch(taskname=taskname, url=url, path=path)


@external
def grib_index_remote(url: str, ts: str):
    yield "%s GRIB index remote %s" % (ts, url)
    yield asset(url, lambda: status(url=url) == 200)


@tasks
def verify_all(config: dict):
    taskname = "Verification"
    variables = set()
    for var in config["variables"]:
        levels = var.get("levels", [None])
        for level in levels:
            variables.add(Var(name=var["name"], levtype=var["levtype"], level=level))
    verify_ones = []
    for tc in timecoords(cycles=config["cycles"], leadtimes=config["leadtimes"]):
        for var in sorted(list(variables)):
            verify_ones.append(
                verify_one(
                    forecast=Path(config["forecast"]),
                    var=var,
                    variables=variables,
                    tc=tc,
                    rundir=Path(config["rundir"]),
                    baseline=config["baseline"],
                )
            )
    yield taskname
    yield verify_ones


@tasks  # PM change to @task
def verify_one(
    forecast: Path, var: Var, variables: set[Var], tc: TimeCoords, rundir: Path, baseline: str
):
    url = baseline.format(yyyymmdd=tc.yyyymmdd, hh=tc.hh)
    fv = forecast_var(var=var, tc=tc, forecast=forecast, rundir=rundir)
    gm = grib_message(var=var, variables=variables, tc=tc, rundir=rundir, url=url)
    yield "Verification of %s at %s" % (var, tc)
    yield [fv, gm]
