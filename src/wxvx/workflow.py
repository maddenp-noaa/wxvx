import logging
from datetime import datetime
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
    for _, v in idxfiles(config, validtimes(config)).items():
        assert v.outputs[0].result().filepath
    parsl.dfk().cleanup()


# Helpers


def genpath(config: dict, tc: TimeCoords) -> str:
    fn = Path(urlparse(genurl(config, tc)).path).name
    return str(Path(config["rundir"], "truth", tc.yyyymmdd, tc.hh, fn))


def genurl(config: dict, tc: TimeCoords) -> str:
    return str(config["baseline"].format(yyyymmdd=tc.yyyymmdd, hh=tc.hh, ff="00"))


@id_for_memo.register(File)
def id_for_memo_file(obj: File, output_ref: bool = False) -> bytes:
    return bytes(obj.filepath, encoding="utf-8")


@id_for_memo.register(Path)
def id_for_memo_path(obj: Path, output_ref: bool = False) -> bytes:
    return bytes(str(obj), encoding="utf-8")


def idxfiles(config: dict, tcs: list[TimeCoords]) -> dict[datetime, AppFuture]:
    return {
        tc.dt: idxfile(
            url=genurl(config, tc) + ".idx",
            outputs=[File(genpath(config, tc) + ".idx")],
        )
        for tc in tcs
    }


# Apps


@python_app  # (cache=True)
def gribfile(url: str, idx: File, outputs: list[File]) -> None:
    logging.info("Would use idxfile %s", idx.filepath)
    fetch(url=url, path=Path(outputs[0]))


@python_app(cache=True)
def idxfile(url: str, outputs: list[File]) -> None:
    fetch(url=url, path=Path(outputs[0]))
