from contextlib import contextmanager
from pathlib import Path
from typing import Generator
from urllib.parse import urlparse

import parsl
from parsl.app.app import python_app
from parsl.config import Config
from parsl.dataflow.memoization import id_for_memo
from parsl.executors import HighThroughputExecutor, ThreadPoolExecutor
from parsl.providers import LocalProvider
from parsl.utils import get_all_checkpoints

from wxvx.net import fetch

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


class ExternalResource(Exception): ...


@id_for_memo.register(Path)
def id_for_memo_path(obj: Path, output_ref: bool = False) -> bytes:
    return bytes(str(obj), encoding="utf-8")


@contextmanager
def run(rundir: Path, config: str) -> Generator:
    r = str(rundir)
    c = configs[config]
    c.checkpoint_files = get_all_checkpoints(r)
    c.run_dir = r
    parsl.clear()
    parsl.load(c)
    yield
    parsl.dfk().cleanup()


# Apps


@python_app(cache=True)
def idxfile(url: str, rundir: Path) -> Path:
    path = rundir / Path(urlparse(url).path).name
    if not fetch(url=url, path=path):
        raise ExternalResource()
    return path
