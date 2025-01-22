from datetime import timedelta
from itertools import pairwise
from pathlib import Path
from urllib.parse import urlparse

from iotaa import asset, external, refs, task

from wxvx.net import fetch, status
from wxvx.time import TimeCoords, validtimes
from wxvx.vars import GFSVar, Var


def go(config: dict) -> None:
    baseline, rundir, variables = [config[x] for x in ("baseline", "rundir", "variables")]
    for tc in validtimes(config):
        grib_index_data(tc=tc, baseline=baseline, fh=0, rundir=Path(rundir), variables=variables)


@task
def grib_index_data(tc: TimeCoords, fh: int, baseline: str, rundir: Path, variables: dict):
    idxdata: set[Var] = set()
    yield "%s GRIB index data" % (tc.dt + timedelta(hours=fh))
    yield asset(idxdata, lambda: bool(idxdata))
    idxfile = grib_index_local(tc=tc, fh=fh, baseline=baseline, rundir=rundir)
    yield idxfile
    required = set(Var(name=v["name"], level=v["level"], levtype=v["levtype"]) for v in variables)
    lines = refs(idxfile).read_text(encoding="utf-8").strip().split("\n")
    lines.append(":-1:::::")  # end marker
    records = [line.split(":") for line in lines]
    for this_record, next_record in pairwise(records):
        var = GFSVar(
            name=GFSVar.stdvar(this_record[3]),
            first_byte=int(this_record[1]),
            last_byte=int(next_record[1]) - 1,
            levstr=this_record[4],
        )
        if var in required:
            idxdata.add(var)


@task
def grib_index_local(tc: TimeCoords, fh: int, baseline: str, rundir: Path):
    url = baseline.format(yyyymmdd=tc.yyyymmdd, hh=tc.hh, fh=f"{fh:02}") + ".idx"
    path = rundir / tc.yyyymmdd / tc.hh / Path(urlparse(url).path).name
    timestamp = tc.dt + timedelta(hours=fh)
    taskname = "%s GRIB index" % timestamp
    yield taskname
    yield asset(path, path.is_file)
    yield grib_index_remote(url=url, timestamp=timestamp)
    fetch(taskname=taskname, url=url, path=path)


@external
def grib_index_remote(url: str, timestamp: str):
    yield "%s GRIB index remote %s" % (timestamp, url)
    yield asset(url, lambda: status(url) == 200)
