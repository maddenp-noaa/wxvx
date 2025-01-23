from datetime import timedelta
from itertools import pairwise
from pathlib import Path
from urllib.parse import urlparse

from iotaa import asset, external, refs, task, tasks

from wxvx.net import fetch, status
from wxvx.time import TimeCoords, validtimes
from wxvx.vars import GFSVar, Var


@tasks
def grib_messages(config: dict):
    fh = 0
    need = set()
    for entry in config["vars"]:
        if levels := entry.get("levels"):
            for level in levels:
                need.add(Var(name=entry["name"], levtype=entry["levtype"], level=level))
        else:
            need.add(Var(name=entry["name"], levtype=entry["levtype"]))
    messages = []
    for tcoord in validtimes(config):
        for var in need:
            url = config["baseline"].format(yyyymmdd=tcoord.yyyymmdd, hh=tcoord.hh, fh=f"{fh:02}")
            messages.append(
                grib_message(
                    var=var,
                    need=need,
                    tcoord=tcoord,
                    rundir=Path(config["rundir"]),
                    url=url,
                    ts=(tcoord.dt + timedelta(hours=fh)).isoformat(),
                )
            )
    yield "GRIB messages"
    yield messages


@task
def grib_message(var: Var, need: set[Var], tcoord: TimeCoords, rundir: Path, url: str, ts: str):
    fn = "%s.dat.%s" % (Path(urlparse(url).path).name, var)
    path = rundir / tcoord.yyyymmdd / tcoord.hh / fn
    idxdata = grib_index_data(need=need, tcoord=tcoord, rundir=rundir, url=f"{url}.idx", ts=ts)
    taskname = "%s GRIB message %s" % (ts, var)
    yield taskname
    yield asset(path, path.is_file)
    yield idxdata
    var_idxdata = refs(idxdata)[str(var)]
    fb, lb = var_idxdata.firstbyte, var_idxdata.lastbyte
    headers = {"Range": "bytes=%s" % (f"{fb}-{lb}" if lb else fb)}
    fetch(taskname=taskname, url=url, path=path, headers=headers)


@task
def grib_index_data(need: set[Var], tcoord: TimeCoords, rundir: Path, url: str, ts: str):
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
        if gfsvar in need:
            idxdata[str(gfsvar)] = gfsvar


@task
def grib_index_local(tcoord: TimeCoords, rundir: Path, url: str, ts):
    path = rundir / tcoord.yyyymmdd / tcoord.hh / Path(urlparse(url).path).name
    taskname = "%s GRIB index local" % ts
    yield taskname
    yield asset(path, path.is_file)
    yield grib_index_remote(url=url, ts=ts)
    fetch(taskname=taskname, url=url, path=path)


@external
def grib_index_remote(url: str, ts: str):
    yield "%s GRIB index remote %s" % (ts, url)
    yield asset(url, lambda: status(url) == 200)
