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
    fd = forecast_dataset(forecast=forecast)
    gm = grib_message(var=var, variables=variables, tcoord=validtime, rundir=rundir, url=url)
    yield "Verification of %s at %s" % (var, validtime)
    yield [fd, gm]
    # _set_cf_metadata(ds, taskname)
