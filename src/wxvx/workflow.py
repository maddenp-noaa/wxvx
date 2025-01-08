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
        initialize_logging=False,
    )
}


@contextmanager
def run(workdir: Path, loader: str) -> Generator:
    config = configs[loader]
    config.run_dir = str(workdir)
    parsl.load(config)
    yield
    parsl.dfk().cleanup()


# Apps


@python_app
def idxfile(url: str, workdir: Path) -> Path:
    path = workdir / Path(urlparse(url).path).name
    fetch(url=url, path=path)
    return path
