import logging
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional
from urllib.parse import urlparse

import parsl
from parsl.app.app import python_app
from parsl.app.futures import DataFuture
from parsl.config import Config
from parsl.data_provider.files import File
from parsl.dataflow.memoization import id_for_memo
from parsl.executors import ThreadPoolExecutor
from parsl.utils import get_all_checkpoints

from wxvx.net import fetch
from wxvx.time import timecoords, validtimes

# Configs

common: dict = dict(
    # checkpoint_mode="task_exit",
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

# PM use generators?


def go(config: dict) -> None:
    rundir = config["rundir"]
    c = configs["threads"]
    # c.checkpoint_files = get_all_checkpoints(rundir)
    c.run_dir = rundir
    parsl.clear()
    parsl.load(c)
    for k, v in idxfiles(config, validtimes(config)).items():
        logging.info("@@@ %s %s", k, v.outputs[0].result().filepath)
    parsl.dfk().cleanup()


# Helpers


@id_for_memo.register(Path)
def id_for_memo_path(obj: Path, output_ref: bool = False) -> bytes:
    return bytes(str(obj), encoding="utf-8")


def idxfiles(config: dict, validtimes: list[datetime]) -> dict[datetime, DataFuture]:
    return {
        validtime: idxfile(
            url=url(config, validtime) + ".idx",
            outputs=[File(path(config, validtime) + ".idx")],
        )
        for validtime in validtimes
    }


def path(config: dict, validtime: datetime) -> str:
    tc = timecoords(validtime)
    return str(
        Path(
            config["rundir"],
            "truth",
            tc.yyyymmdd,
            tc.hh,
            Path(urlparse(url(config, validtime)).path).name,
        )
    )


def url(config: dict, validtime: datetime) -> str:
    tc = timecoords(validtime)
    return config["baseline"].format(yyyymmdd=tc.yyyymmdd, hh=tc.hh, ff="00")


# Apps


@python_app  # (cache=True)
def gribfile(url: str, idxfile: File, outputs: list[File]) -> None:
    logging.info("Would use idxfile %s", idxfile.filepath)
    fetch(url=url, path=Path(outputs[0]))


@python_app  # (cache=True)
def idxfile(url: str, outputs: list[File]) -> None:
    fetch(url=url, path=Path(outputs[0]))
