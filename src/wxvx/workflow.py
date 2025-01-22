from datetime import timedelta
from itertools import pairwise
from pathlib import Path
from urllib.parse import urlparse

from iotaa import asset, external, refs, task

from wxvx.net import fetch, status
from wxvx.time import TimeCoords, validtimes
from wxvx.vars import GFSVar, Var


def go(config: dict) -> None:
    fh = 0
    for tcoord in validtimes(config):
        grib_message(
            url=config["baseline"].format(yyyymmdd=tcoord.yyyymmdd, hh=tcoord.hh, fh=f"{fh:02}"),
            timestamp=(tcoord.dt + timedelta(hours=fh)).isoformat(),
            tcoord=tcoord,
            rundir=Path(config["rundir"]),
            required=set(
                Var(name=v["name"], level=v["level"], levtype=v["levtype"])
                for v in config["variables"]
            ),
        )


@task
def grib_message(url: str, timestamp: str, tcoord: TimeCoords, rundir: Path, required: set[Var]):
    path = rundir / tcoord.yyyymmdd / tcoord.hh / Path(urlparse(url).path).name
    idxdata = grib_index_data(
        url=url + ".idx",
        timestamp=timestamp,
        tcoord=tcoord,
        rundir=rundir,
        required=required,
    )
    yield "%s GRIB message" % timestamp
    yield asset(path, path.is_file)
    yield idxdata
    path.touch()


@task
def grib_index_data(url: str, timestamp: str, tcoord: TimeCoords, rundir: Path, required: set[Var]):
    idxdata: set[Var] = set()
    idxfile = grib_index_local(url=url, timestamp=timestamp, tcoord=tcoord, rundir=rundir)
    yield "%s GRIB index data" % timestamp
    yield asset(idxdata, lambda: bool(idxdata))
    yield idxfile
    lines = refs(idxfile).read_text(encoding="utf-8").strip().split("\n")
    lines.append(":-1:::::")  # end marker
    for this_record, next_record in pairwise([line.split(":") for line in lines]):
        var = GFSVar(
            name=GFSVar.stdvar(this_record[3]),
            first_byte=int(this_record[1]),
            last_byte=int(next_record[1]) - 1,
            levstr=this_record[4],
        )
        if var in required:
            idxdata.add(var)


@task
def grib_index_local(url: str, timestamp: str, tcoord: TimeCoords, rundir: Path):
    path = rundir / tcoord.yyyymmdd / tcoord.hh / Path(urlparse(url).path).name
    taskname = "%s GRIB index" % timestamp
    yield taskname
    yield asset(path, path.is_file)
    yield grib_index_remote(url=url, timestamp=timestamp)
    fetch(taskname=taskname, url=url, path=path)


@external
def grib_index_remote(url: str, timestamp: str):
    yield "%s GRIB index remote %s" % (timestamp, url)
    yield asset(url, lambda: status(url) == 200)
