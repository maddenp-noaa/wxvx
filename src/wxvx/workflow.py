# import logging
from itertools import pairwise
from pathlib import Path
from urllib.parse import urlparse

import parsl
from parsl.app.app import python_app
from parsl.config import Config
from parsl.data_provider.files import File

# from parsl.dataflow.futures import AppFuture
from parsl.dataflow.memoization import id_for_memo
from parsl.executors import ThreadPoolExecutor
from parsl.utils import get_all_checkpoints

from wxvx.net import fetch
from wxvx.strings import STR
from wxvx.time import TimeCoords, validtimes
from wxvx.vars import GFSVar, Var

# Configs

common: dict = dict(
    checkpoint_mode="task_exit",
    initialize_logging=False,
    usage_tracking=0,
)

configs = {
    STR.threads: Config(
        **common,
        executors=[ThreadPoolExecutor(max_threads=4)],
    ),
}

# Main


def go(config: dict) -> None:
    c = configs[STR.threads]
    c.run_dir = config["rundir"]
    c.checkpoint_files = get_all_checkpoints(c.run_dir)
    rundir = Path(c.run_dir)
    parsl.clear()
    parsl.load(c)
    idxfiles = {}
    for tc in validtimes(config):
        url = genurl(tc=tc, baseline=config["baseline"], suffix=".idx")
        f = genfile(tc=tc, rundir=rundir, url=url)
        idxfiles[tc] = get_idxfile(url=url, outputs=[f]).outputs[0]
    idxdata = {}
    for tc in validtimes(config):
        idxdata[tc] = get_idxdata(idxfiles[tc], variables=config["variables"])
    for x in idxdata.values():
        x.result()
    parsl.dfk().cleanup()


# Helpers


def genfile(tc: TimeCoords, rundir: Path, url: str) -> File:
    return File(rundir / tc.yyyymmdd / tc.hh / Path(urlparse(url).path).name)


def genurl(tc: TimeCoords, baseline: str, suffix: str = "") -> str:
    return baseline.format(yyyymmdd=tc.yyyymmdd, hh=tc.hh, ff="00") + suffix


@id_for_memo.register(File)
def id_for_memo_file(obj: File, output_ref: bool = False) -> bytes:
    return bytes(obj.filepath, encoding="utf-8")


@id_for_memo.register(Path)
def id_for_memo_path(obj: Path, output_ref: bool = False) -> bytes:
    return bytes(str(obj), encoding="utf-8")


# Apps


@python_app(cache=True)
def get_idxdata(f: File, variables: dict) -> set[Var]:
    required = set(Var(name=v["name"], level=v["level"], levtype=v["levtype"]) for v in variables)
    lines = Path(f.filepath).read_text(encoding="utf-8").strip().split("\n")
    lines.append(":-1:::::")  # end marker
    records = [line.split(":") for line in lines]
    vs = set()
    for a, b in pairwise(records):
        v = GFSVar(
            name=GFSVar.stdvar(a[3]), first_byte=int(a[1]), last_byte=int(b[1]) - 1, levstr=a[4]
        )
        if v in required:
            vs.add(v)
    return vs


@python_app(cache=True)
def get_idxfile(url: str, outputs: list[File]) -> None:
    fetch(url=url, path=Path(outputs[0]))
