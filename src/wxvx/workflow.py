from contextlib import contextmanager
from pathlib import Path
from typing import Generator
from urllib.parse import urlparse

import parsl
from parsl.app.app import python_app
from parsl.config import Config
from parsl.executors import ThreadPoolExecutor

from wxvx.net import fetch

# Helpers

configs = {
    "threads": Config(
        executors=[ThreadPoolExecutor(max_threads=4)],
        exit_mode="wait",
        initialize_logging=False,
    )
}


@contextmanager
def run(rundir: Path, loader: str) -> Generator:
    config = configs[loader]
    config.run_dir = str(rundir)
    with parsl.load(config):
        yield


# Apps


@python_app
def idxfile(url: str, rundir: Path) -> Path:
    path = rundir / Path(urlparse(url).path).name
    fetch(url=url, path=path)
    return path
