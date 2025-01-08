from contextlib import contextmanager
from pathlib import Path
from typing import Generator
from urllib.parse import urlparse

import parsl
from parsl.app.app import python_app
from parsl.config import Config
from parsl.dataflow.memoization import id_for_memo
from parsl.executors import ThreadPoolExecutor
from parsl.utils import get_all_checkpoints

from wxvx.net import fetch

# Configs

configs = {
    "threads": Config(
        checkpoint_mode="task_exit",
        executors=[ThreadPoolExecutor(max_threads=4)],
        exit_mode="wait",
        initialize_logging=False,
    )
}

# Helpers


@id_for_memo.register(Path)
def id_for_memo_path(obj: Path, output_ref: bool = False) -> bytes:
    return bytes(str(obj), encoding="utf-8")


@contextmanager
def run(rundir: Path, loader: str) -> Generator:
    r = str(rundir)
    config = configs[loader]
    config.checkpoint_files = get_all_checkpoints(r)
    config.run_dir = r
    parsl.load(config)
    yield
    parsl.dfk().cleanup()


# Apps


@python_app(cache=True)
def idxfile(url: str, rundir: Path) -> Path:
    path = rundir / Path(urlparse(url).path).name
    fetch(url=url, path=path)
    return path
