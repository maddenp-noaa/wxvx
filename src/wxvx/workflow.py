import logging
from pathlib import Path
from typing import Iterator
from urllib.parse import urlparse

import parsl
from parsl.app.app import python_app
from parsl.config import Config
from parsl.dataflow.memoization import id_for_memo
from parsl.executors import HighThroughputExecutor, ThreadPoolExecutor
from parsl.providers import LocalProvider
from parsl.utils import get_all_checkpoints

from wxvx.net import fetch
from wxvx.time import validtimes

# Configs

common: dict = dict(
    checkpoint_mode="task_exit",
    initialize_logging=False,
    usage_tracking=0,
)

configs = {
    "htx": Config(
        **common,
        executors=[HighThroughputExecutor(provider=LocalProvider(), worker_debug=True)],
    ),
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
    c.checkpoint_files = get_all_checkpoints(rundir)
    c.run_dir = rundir
    # parsl.clear()
    parsl.load(c)
    futures = [idxfile(url=f"{x}.idx", rundir=rundir) for x in truth(config)]
    for f in futures:
        try:
            path = f.result()
        except ExternalResourceError:
            pass
        else:
            logging.info("Got %s: %s", path, path.is_file())
    parsl.dfk().cleanup()


def truth(config: dict) -> Iterator[str]:
    for x in sorted(validtimes(config)):
        yield config["baseline"].format(yyyymmdd=x.strftime("%Y%m%d"), hh=x.strftime("%H"), ff="00")


# Apps


@python_app(cache=True)
def idxfile(url: str, rundir: Path) -> Path:
    path = Path(rundir, Path(urlparse(url).path).name)
    if not fetch(url=url, path=path):
        raise ExternalResourceError()
    return path
