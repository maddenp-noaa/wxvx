import logging
from pathlib import Path
from urllib.parse import urlparse

import parsl
from parsl.app.app import python_app
from parsl.config import Config
from parsl.data_provider.files import File
from parsl.dataflow.futures import AppFuture
from parsl.dataflow.memoization import id_for_memo
from parsl.executors import ThreadPoolExecutor
from parsl.utils import get_all_checkpoints

from wxvx.net import fetch
from wxvx.time import TimeCoords, validtimes

# Configs

common: dict = dict(
    checkpoint_mode="task_exit",
    initialize_logging=False,
    usage_tracking=0,
)

configs = {
    "threads": Config(
        **common,
        executors=[ThreadPoolExecutor(max_threads=4)],
    ),
}

# Main


def go(config: dict) -> None:
    rundir = config["rundir"]
    c = configs["threads"]
    c.checkpoint_files = get_all_checkpoints(rundir)
    c.run_dir = rundir
    parsl.clear()
    parsl.load(c)
    for _, v in idxfiles(config["baseline"], Path(config["rundir"]), validtimes(config)).items():
        assert v.outputs[0].result().filepath
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


def idxfiles(baseline: str, rundir: Path, tcs: list[TimeCoords]) -> dict[TimeCoords, AppFuture]:
    files = {}
    for tc in tcs:
        url = genurl(tc=tc, baseline=baseline, suffix=".idx")
        f = genfile(tc=tc, rundir=rundir, url=url)
        files[tc] = idxfile(url=url, outputs=[f])
    return files


# Apps


@python_app(cache=True)
def gribfile(url: str, idx: File, outputs: list[File]) -> None:
    logging.info("Would use idxfile %s", idx.filepath)
    fetch(url=url, path=Path(outputs[0]))


@python_app
def idxdata(f: File) -> str:
    return Path(f.filepath).read_text(encoding="utf-8")


@python_app(cache=True)
def idxfile(url: str, outputs: list[File]) -> None:
    fetch(url=url, path=Path(outputs[0]))
