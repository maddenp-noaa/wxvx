import logging
from pathlib import Path
from typing import Iterator, Optional
from urllib.parse import urlparse

import parsl
from parsl.app.app import python_app
from parsl.config import Config
from parsl.dataflow.memoization import id_for_memo
from parsl.executors import ThreadPoolExecutor
from parsl.utils import get_all_checkpoints
from parsl.data_provider.files import File
from wxvx.net import fetch
from wxvx.time import validtimes
from parsl.app.futures import DataFuture
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

# Helpers


class ExternalResourceError(Exception): ...


@id_for_memo.register(Path)
def id_for_memo_path(obj: Path, output_ref: bool = False) -> bytes:
    return bytes(str(obj), encoding="utf-8")


def go(config: dict) -> None:
    rundir = config["rundir"]
    c = configs["threads"]
    # c.checkpoint_files = get_all_checkpoints(rundir)
    c.run_dir = rundir
    parsl.clear()
    parsl.load(c)
    futures = []
    for validtime in validtimes(config):
        yyyymmdd = validtime.strftime("%Y%m%d")
        hh = validtime.strftime("%H")
        gribfile_url = config["baseline"].format(yyyymmdd=yyyymmdd, hh=hh, ff="00")
        gribfile_path = Path(rundir, "truth", yyyymmdd, hh, Path(urlparse(gribfile_url).path).name)
        idxfile_url = gribfile_url + ".idx"
        idxfile_path = Path(rundir, "truth", yyyymmdd, hh, Path(urlparse(idxfile_url).path).name)
        idxfile_future = idxfile(url=idxfile_url, outputs=[File(idxfile_path)])
        gribfile_future = gribfile(url=gribfile_url, idxfile_path_future=idxfile_future.outputs[0], outputs=[File(gribfile_path)])
        futures.append(gribfile_future)
    for future in futures:
        assert future.result() is None
        path = Path(future.outputs[0].result().filepath)
        logging.info("Got %s: %s", path, path.is_file())
    parsl.dfk().cleanup()


def urls(config: dict) -> Iterator[str]:
    for x in validtimes(config):
        yield config["baseline"].format(yyyymmdd=x.strftime("%Y%m%d"), hh=x.strftime("%H"), ff="00")


# Apps


@python_app #(cache=True)
def idxfile(url: str, outputs: list[File]) -> None:
    fetch(url=url, path=Path(outputs[0]))


@python_app #(cache=True)
def gribfile(url: str, idxfile_path_future: DataFuture, outputs: list[File]) -> None:
    logging.info("Would use idxfile %s", idxfile_path_future.filepath)
    fetch(url=url, path=Path(outputs[0]))
