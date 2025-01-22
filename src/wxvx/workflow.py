# from itertools import pairwise
from pathlib import Path
from urllib.parse import urlparse

from iotaa import asset, external, task

from wxvx.net import fetch, status

# from wxvx.strings import STR
from wxvx.time import TimeCoords, validtimes

# from wxvx.vars import GFSVar, Var


def go(config: dict) -> None:
    for tc in validtimes(config):
        grib_index_local(tc=tc, baseline=config["baseline"], rundir=Path(config["rundir"]))


@task
def grib_index_local(tc: TimeCoords, baseline: str, rundir: Path):
    url = baseline.format(yyyymmdd=tc.yyyymmdd, hh=tc.hh, ff="00") + ".idx"
    path = rundir / tc.yyyymmdd / tc.hh / Path(urlparse(url).path).name
    taskname = "GRIB index local: %s" % path
    yield taskname
    yield asset(path, path.is_file)
    yield grib_index_remote(url=url)
    fetch(taskname=taskname, url=url, path=path)


@external
def grib_index_remote(url: str):
    yield "GRIB index remote: %s" % url
    yield asset(url, lambda: status(url) == 200)
